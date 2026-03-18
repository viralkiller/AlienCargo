# _Blog_Functions.py
import os
import time
import requests
import json
import random
from _Utils import acquire_lock, release_lock

STATE_DIR = '/tmp/aliencargo_state'
BLOG_LOCK_FILE = os.path.join(STATE_DIR, 'blog.lock')
# Fallback URL with encoded spaces
FALLBACK_IMAGE_URL = 'https://blogmanager.pythonanywhere.com/static/images/thumbs/generic%20laptop%20with%20blog%20written%20on%20the%20screen.png'

class Blog_Functions:
    def __init__(self):
        print("DEBUG: Initializing Blog_Functions...")
        self.api_url = 'https://blogmanager.pythonanywhere.com/request_blog_post'
        self.hashtags_api_url = 'https://blogmanager.pythonanywhere.com/process_hashtags'
        self.creation_time_limit = 1 * 3600
        self.topics = [
            "Where can I find an AI game generator?",
        ]
        self.author = 'James Gordon'
        self.blog_data_path = 'static/json/blog_data/blog_data.json'

        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.blog_data_path), exist_ok=True)
        print(f"DEBUG: Blog data path set to: {self.blog_data_path}")
        print(f"DEBUG: Fallback image URL set to: {FALLBACK_IMAGE_URL}")

    def get_blog_data(self):
        """Safely reads and returns all blog data from the JSON file. Does NOT validate image URLs here."""
        print(f"DEBUG: Reading blog data from {self.blog_data_path}")
        if not os.path.exists(self.blog_data_path):
            print("WARNING: blog_data.json does not exist. Returning empty list.")
            return []

        blog_data = [] # Initialize as empty list

        try:
            with open(self.blog_data_path, 'r', encoding='utf-8') as file:
                content = file.read()
                if not content.strip(): # Check if the file is empty or just whitespace
                    print("WARNING: blog_data.json is empty. Returning empty list.")
                    return []

                # Attempt to parse JSON
                parsed_data = json.loads(content)
                if not isinstance(parsed_data, list):
                    print("ERROR: blog_data.json does not contain a valid JSON list. Returning empty list.")
                    return [] # Ensure it's always a list

                blog_data = parsed_data # Assign parsed data if valid
                print(f"DEBUG: Successfully read {len(blog_data)} blog entries.")

        except json.JSONDecodeError as e:
            print(f"ERROR: Could not parse blog_data.json: {e}. File content might be corrupt. Returning empty list.")
            return []
        except IOError as e:
            print(f"ERROR: Could not read blog_data.json: {e}. Returning empty list.")
            return []
        except Exception as e:
            print(f"ERROR: An unexpected error occurred while reading blog data: {e}. Returning empty list.")
            return []

        print("DEBUG: Blog data read complete (no URL modification).")
        return blog_data

    def request_blog_data(self, topic):
        """Calls the microservice to get blog content for a specific topic,
           applying fallback image URL if the received one is missing or empty."""
        print(f"DEBUG: Requesting blog data for topic: '{topic}' from {self.api_url}")
        try:
            payload = {'topic': topic, 'author': self.author}
            response = requests.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()

            blog_entry = response.json()
            print(f"DEBUG: Successfully received blog data from microservice for topic '{topic}'.")

            if not isinstance(blog_entry, dict) or 'title' not in blog_entry or 'main_text' not in blog_entry:
                print("ERROR: Received invalid blog entry format from microservice.")
                return None

            # --- Check if image URL exists and is non-empty ---
            original_url = blog_entry.get('blog_image')
            if not original_url or not isinstance(original_url, str) or not original_url.strip():
                 print(f"WARNING: Received entry (Title: '{blog_entry.get('title', 'N/A')[:30]}...') has missing or empty image URL from API. Using fallback BEFORE saving.")
                 blog_entry['blog_image'] = FALLBACK_IMAGE_URL
            # --------------------------------------------------

            return blog_entry

        except requests.exceptions.Timeout:
            print(f"ERROR: Blog data request timed out after 120 seconds for topic '{topic}'.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"ERROR: An error occurred while fetching blog data for topic '{topic}': {e}")
            return None
        except json.JSONDecodeError:
            print(f"ERROR: Failed to decode JSON response from blog microservice for topic '{topic}'. Response text: {response.text[:200]}")
            return None

    def can_create_new_entry(self):
        """Checks if a new blog entry can be created based on the creation time limit."""
        print("DEBUG: Checking if a new blog entry can be created...")
        if not os.path.exists(self.blog_data_path):
            print(f"DEBUG: Blog data file not found at '{self.blog_data_path}'. Allowing new entry.")
            return True

        try:
            # Check file size first to avoid reading large empty/corrupt files
            if os.path.getsize(self.blog_data_path) == 0:
                 print("DEBUG: blog_data.json is empty (0 bytes). Allowing new entry.")
                 return True

            with open(self.blog_data_path, 'r', encoding='utf-8') as file:
                content = file.read()
                if not content.strip():
                    print("DEBUG: blog_data.json contains only whitespace. Allowing new entry.")
                    return True
                blog_data = json.loads(content)

            if not isinstance(blog_data, list) or not blog_data:
                print("DEBUG: blog_data.json is not a list or is empty after parsing. Allowing new entry.")
                return True

            # Get the timestamp of the *most recent* entry (first in the list)
            last_entry_time = blog_data[0].get('unix_timestamp', 0)

            if not isinstance(last_entry_time, (int, float)) or last_entry_time <= 0:
                print("WARNING: Invalid or missing timestamp in the most recent blog entry. Allowing new entry.")
                return True

            current_unix_timestamp = int(time.time())
            time_since_last = current_unix_timestamp - last_entry_time
            remaining_time = self.creation_time_limit - time_since_last

            print(f"DEBUG: Current time: {current_unix_timestamp}, Last entry time: {last_entry_time}")
            print(f"DEBUG: Time since last post: {time_since_last}s. Limit: {self.creation_time_limit}s.")

            if time_since_last > self.creation_time_limit:
                print("DEBUG: Time limit exceeded. Allowing new entry.")
                return True
            else:
                print(f"DEBUG: Time limit not yet exceeded. Need to wait {remaining_time} more seconds. Not creating new entry.")
                return False

        except json.JSONDecodeError as e:
            print(f"ERROR: Reading or parsing blog_data.json failed: {e}. Allowing new entry as a fallback.")
            return True
        except (IOError, IndexError, TypeError) as e:
             print(f"ERROR: Problem accessing blog data or its contents: {e}. Allowing new entry as a fallback.")
             return True
        except Exception as e:
            print(f"ERROR: An unexpected error occurred in can_create_new_entry: {e}. Allowing new entry as a fallback.")
            return True

    def create_blog_entry(self):
        """
        Creates a new blog entry by calling the microservice (which includes image validation)
        and updates the local JSON file. Protected by a file lock.
        """
        print("DEBUG: Attempting to create a new blog entry...")
        if not acquire_lock(BLOG_LOCK_FILE):
            print("ERROR: Could not acquire blog lock. Another process may be creating a post or the lock is stale. Aborting.")
            return

        try:
            if self.can_create_new_entry():
                print("DEBUG: Condition met. Proceeding to request a new blog entry.")
                topic = random.choice(self.topics)
                print(f"DEBUG: Selected random topic: '{topic}'")

                # request_blog_data now includes the check for missing/empty image URL
                blog_entry = self.request_blog_data(topic)

                if blog_entry and "error" not in blog_entry:
                    print("DEBUG: Received valid blog entry from microservice (image URL potentially corrected). Updating local data.")
                    self.update_blog_data(blog_entry)
                elif blog_entry and "error" in blog_entry:
                     print(f"ERROR: Microservice returned an error: {blog_entry.get('error')}")
                else:
                    print("ERROR: Failed to create blog entry. No data returned from the API or API returned an error.")
            else:
                print("DEBUG: Condition not met (time limit not exceeded). No new blog entry needed at this time.")
        except Exception as e:
             print(f"ERROR: An unexpected error occurred during create_blog_entry: {e}")
        finally:
            release_lock(BLOG_LOCK_FILE)
            print("DEBUG: Blog lock released.")

    def update_blog_data(self, new_entry):
        """Updates the blog data JSON file with a new entry, prepending it to the list."""
        print("DEBUG: Updating local blog_data.json file with new entry...")

        # Read existing data (without modifying URLs here)
        blog_data = self.get_blog_data()

        # Ensure new_entry has a timestamp if it's missing
        if 'unix_timestamp' not in new_entry:
            print("WARNING: New blog entry is missing 'unix_timestamp'. Adding current time.")
            new_entry['unix_timestamp'] = int(time.time())

        # Image URL should have already been checked/corrected in request_blog_data
        # Add a final safety check before writing
        if not new_entry.get('blog_image') or not isinstance(new_entry.get('blog_image'), str) or not new_entry.get('blog_image').strip():
             print(f"WARNING: New blog entry (Title: '{new_entry.get('title', 'N/A')[:30]}...') still has missing/empty image URL before saving. Using fallback.")
             new_entry['blog_image'] = FALLBACK_IMAGE_URL

        # Prepend the new entry to the existing list
        blog_data.insert(0, new_entry)
        print(f"DEBUG: Blog data now contains {len(blog_data)} entries after insertion.")

        # Write the updated list back to the file
        temp_file_path = self.blog_data_path + ".tmp"
        try:
            # Write to temporary file first
            with open(temp_file_path, 'w', encoding='utf-8') as file:
                json.dump(blog_data, file, indent=4, ensure_ascii=False) # Use indent for readability

            # Atomically replace the old file with the new one
            os.replace(temp_file_path, self.blog_data_path)
            print("DEBUG: Successfully wrote updated blog data to blog_data.json.")

        except IOError as e:
            print(f"ERROR: Could not write to blog_data.json: {e}")
            # Attempt cleanup of temp file on write error
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError as cleanup_e:
                     print(f"ERROR: Failed to remove temporary file '{temp_file_path}' after write error: {cleanup_e}")
        except Exception as e:
             print(f"ERROR: An unexpected error occurred during update_blog_data write: {e}")
             if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError as cleanup_e:
                     print(f"ERROR: Failed to remove temporary file '{temp_file_path}' after unexpected write error: {cleanup_e}")
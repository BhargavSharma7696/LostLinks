import base64
import uuid
import database

def upload_photo(photo_file, photo_base64):
    try:
        if photo_base64 and photo_base64.strip():
            header, encoded = photo_base64.split(",", 1)
            file_data = base64.b64decode(encoded)

            content_type = header.split(";")[0].split(":")[1]
            extension = content_type.split("/")[-1]

        elif photo_file and photo_file.filename:
            file_data = photo_file.read()
            content_type = photo_file.content_type or "image/png"
            extension = content_type.split("/")[-1]

        else:
            return None

        filename = f"{uuid.uuid4()}.{extension}"

        database.supabase.storage.from_("lost-items").upload(
            path=filename,
            file=file_data,
            file_options={"content-type": content_type}
        )

        public_url = database.supabase.storage.from_("lost-items").get_public_url(filename)

        return public_url

    except Exception as e:
        print(f"Error uploading photo to Supabase Storage: {e}")
        return None
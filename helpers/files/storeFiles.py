import os
import uuid

from fastapi import UploadFile


CHUNK_SIZE = 1024 * 1024 


async def storeFiles(upload_path:str,file : UploadFile) -> str:

    if not os.path.isdir(upload_path):
        os.makedirs(upload_path)


    extension = os.path.splitext(file.filename or "")[1].lower()
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = os.path.join(upload_path, stored_name)

    with open(destination, "wb") as out:
        while chunk := await file.read(CHUNK_SIZE):
            out.write(chunk)

    await file.close()

    return stored_name


def deleteStoredFile(upload_path:str,thumbnail_path:str) -> None:

    # basename() keeps the delete inside the upload folder whatever the DB holds
    filename = os.path.basename(thumbnail_path)
    destination = os.path.join(upload_path, filename)

    if filename and os.path.isfile(destination):
        os.remove(destination)

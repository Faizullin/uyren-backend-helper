# app/routes/google_auth.py
from fastapi import APIRouter, Body
from ..services.content_ml_helper import get_content_ml_auth_file_path, google_login, run_notebook_lm
import os
import pathlib

router = APIRouter()

@router.post("/login/google")
def login_google():
    result = google_login()
    return {"message": result}

@router.post("/notebooklm/ask")
def ask_notebooklm(
    question: str = Body(..., embed=True),
):
    ETHICS_NOTE_ID = "c064442d-4be6-4ec6-a86b-1bfe6e79c762?_gl=1*lbkka4*_ga*Njc5MjA3NjEwLjE3NDE3OTk1MjE.*_ga_W0LDH41ZCB*czE3NTA5Nzg2NDIkbzMkZzAkdDE3NTA5Nzg2NDIkajYwJGwwJGgw"
    STATE = get_content_ml_auth_file_path()
    result = run_notebook_lm(note_id = ETHICS_NOTE_ID, question = question, state_path = STATE)
    return {"result": result}
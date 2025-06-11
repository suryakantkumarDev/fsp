from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from utils.token_utils import SECRET_KEY, ALGORITHM

# Update tokenUrl to match the API prefix
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")  # Changed from "api/auth/login"

async def validate_token(token: str = Depends(oauth2_scheme)) -> tuple[str, dict]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id, payload
    except JWTError:
        raise credentials_exception

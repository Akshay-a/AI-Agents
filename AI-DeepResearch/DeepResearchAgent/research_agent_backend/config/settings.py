from pydantic import Field
from pydantic_settings import BaseSettings
OUTPUT_DIR="\\research_agent_backend\\LLM_outputs\\"
#removing BaseSettings inheritance as its throwing errror
class DBSettings():
    """
    Database configuration settings loaded from environment variables.
    Supports both SQLite and PostgreSQL configurations.
    """
    
    # For SQLite
    DATABASE_URL: str = "sqlite:///./research_agent.db"
    
    """
    DATABASE_URL: str = Field(
        default="sqlite:///./research_agent.db",
        description="Database connection string. For SQLite: 'sqlite:///./filename.db'"
    )
    # For future PostgreSQL support
    DB_USER: str = Field(
        default="",
        description="PostgreSQL username"
    )
    DB_PASSWORD: str = Field(
        default="",
        description="PostgreSQL password"
    )
    DB_HOST: str = Field(
        default="localhost",
        description="PostgreSQL host"
    )
    DB_PORT: str = Field(
        default="5432",
        description="PostgreSQL port"
    )
    DB_NAME: str = Field(
        default="research_agent",
        description="PostgreSQL database name"
    )
    
    @property
    def postgres_dsn(self) -> str:
        
        Constructs a PostgreSQL connection string from component parts.
        Only used if DATABASE_URL is not explicitly set.
        
        if not self.DB_USER:
            return ""
        
        # Construct PostgreSQL connection string
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    """

    @property
    def connection_string(self) -> str:
        #if self.DATABASE_URL and not self.DATABASE_URL.startswith("postgresql"):
        #    return self.DATABASE_URL
            
        # Default to the SQLite URL
        return self.DATABASE_URL
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8" 
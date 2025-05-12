from pydantic import BaseSettings, Field


class DBSettings(BaseSettings):
    """
    Database configuration settings loaded from environment variables.
    Supports both SQLite and PostgreSQL configurations.
    """
    
    # For SQLite
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
        """
        Constructs a PostgreSQL connection string from component parts.
        Only used if DATABASE_URL is not explicitly set.
        """
        if not self.DB_USER:
            return ""
        
        # Construct PostgreSQL connection string
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def connection_string(self) -> str:
        """
        Returns the appropriate database connection string.
        If DATABASE_URL is explicitly set, that is used.
        Otherwise, if PostgreSQL credentials are set, the postgres_dsn is used.
        """
        if self.DATABASE_URL and not self.DATABASE_URL.startswith("postgresql"):
            return self.DATABASE_URL
            
        pg_dsn = self.postgres_dsn
        if pg_dsn:
            return pg_dsn
            
        # Default to the SQLite URL
        return self.DATABASE_URL
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8" 
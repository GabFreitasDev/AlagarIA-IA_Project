from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Substitua 'senha' e 'recife_gis' caso tenha usado credenciais diferentes no Docker
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:senha@localhost:5432/recife_gis"

# O 'engine' é o motor do SQLAlchemy que gerencia a comunicação com o PostgreSQL
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# O 'SessionLocal' será usado para criar sessões de banco de dados temporárias a cada requisição na API
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# A 'Base' é a classe raiz que usaremos para criar nossas tabelas no arquivo models.py
Base = declarative_base()
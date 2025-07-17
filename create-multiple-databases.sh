#!/bin/bash
set -e

# Выполняем SQL-команду для создания второй базы данных 'planning_db'
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE planning_db;
EOSQL
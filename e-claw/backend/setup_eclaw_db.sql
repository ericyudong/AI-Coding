-- Create e-claw database and user
CREATE USER eclaw WITH PASSWORD 'eclaw';
CREATE DATABASE eclaw OWNER eclaw;
GRANT ALL PRIVILEGES ON DATABASE eclaw TO eclaw;
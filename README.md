# Banking Operations Monitor

## Setup Instructions

### 1. Clone the Repository

If you haven’t already downloaded the project, clone it using Git. Open your terminal and run:

```bash
git clone <repository-url>
cd <repository-directory>

```

### Docker Easy Setup (SHORTCUT)

```bash

docker build -t banking_operations_monitor .
docker run -p 8000:8000 banking_operations_monitor

```

*(Replace `<repository-url>` with the URL of the repository and `<repository-directory>` with the folder name.)*

### 2. Create a Virtual Environment 

A virtual environment isolates the project’s dependencies from other Python projects on your system.

- **On Windows:**

  ```bash
  python -m venv env
  ```

- **On macOS/Linux:**

  ```bash
  python3 -m venv env
  ```

### 3. Activate the Virtual Environment

Activate your virtual environment to ensure you're using the correct Python interpreter and packages.

- **On Windows (Command Prompt):**

  ```bash
  env\Scripts\activate
  ```

- **On Windows (PowerShell):**

  ```powershell
  .\env\Scripts\activate
  ```

- **On macOS/Linux:**

  ```bash
  source env/bin/activate
  ```

When activated, your terminal prompt should start with `(env)`.

### 4. Install Dependencies

Install the necessary Python packages using `pip`. If the project includes a `requirements.txt` file, run:

```bash
pip install -r requirements.txt
```

If there is no `requirements.txt`, install Django manually:

```bash
pip install django
```

### 5. Run Database Migrations

Even if your project doesn’t heavily rely on the database, it’s good practice to run migrations:

```bash
python manage.py migrate
```

### 6. Start the Development Server

Run the following command to start the Django development server:

```bash
python manage.py runserver
```

You should see output like this:

```
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

### 7. Visit the Application in Your Browser

Open your web browser and go to [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/en/5.1/)
- [Python Virtual Environments](https://docs.python.org/3/library/venv.html)

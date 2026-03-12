# mini-rag

This is Rag application for question answering that follows MVC architecture.

# Technologies Used

## 1. LLM Providers
- CoHere generation client used for text generation.
- CoHere embedding client used for text embedding to vector database.

## 2. MongoDB
Used for:
- Storing documents and their metadata
- Storing documents chunks

## 3. QDRANT vector database
Used for:
- Storing text embeddings in vector database
- Vector search

# Project design
### MVC architecture
A software architectural design pattern that separates an application into three interconnected components—Model (data), View (UI), and Controller (logic)—to separate business logic from user interface, enhancing.
- <b>Models</b>: Manages the application's data, business rules, logic, and database interactions. It directly manages the data, logic, and rules of the application.
- <b>View</b>: Displays the data (Model) to the user and sends user actions to the Controller. It is the user interface, such as HTML/CSS in web apps.
- <b>Controller</b>:  Acts as an intermediary, processing input from the user (via the View), updating the Model, and selecting a view to render. It handles input validation and application logic

## Requirements

- Python 3.8 or later

#### Install Python using MiniConda

1) Download and install MiniConda from [here](https://docs.anaconda.com/free/miniconda/#quick-command-line-install)
2) Create a new environment using the following command:
```bash
$ conda create -n mini-rag python=3.8
```
3) Activate the environment:
```bash
$ conda activate mini-rag-app
```

## Installation

### Install the required packages

```bash
$ pip install -r requirements.txt
```

### Setup the environment variables

```bash
$ cp .env.example .env
```

Set your environment variables in the `.env` file. Like `OPENAI_API_KEY` value.

## Run Docker Compose Services

```bash
$ cd docker
$ cp .env.example .env
```

- update `.env` with your credentials


```bash
$ cd docker
$ sudo docker compose up -d
```

## Run the FastAPI server

```bash
$ uvicorn main:app --reload --host 0.0.0.0 --port 5000
```
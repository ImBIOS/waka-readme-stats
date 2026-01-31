FROM python:3.13-alpine

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create assets directory
RUN mkdir -p /waka-readme-stats/assets

# Install build dependencies
RUN apk add --no-cache g++ jpeg-dev zlib-dev libjpeg make git

WORKDIR /waka-readme-stats

# Copy Pipenv files
COPY Pipfile Pipfile.lock ./

# Install pipenv and dependencies into the system environment
RUN pip install pipenv && \
  pipenv install --deploy --system

# Copy the source code
COPY sources/ ./sources/

# Configure git for actions
RUN git config --global user.name "readme-bot" && \
  git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"

ENTRYPOINT ["python3", "/waka-readme-stats/sources/main.py"]

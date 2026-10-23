# Show available recipes
default:
    @just --list --unsorted

# Run all available recipes
all: lint typecheck test coverage build docs-build

# Sync development dependencies (may update uv.lock if pyproject.toml changed)
sync *ARGS:
    uv sync {{ARGS}} --group dev

# Lint and format source code
lint:
    uv run ruff check --fix src/ tests/ plugins/
    uv run ruff format src/ tests/ plugins/

# Run static type checks with Astral ty
typecheck:
    uv run ty check src/ plugins/

# Run tests
test *ARGS:
    uv run pytest -v {{ARGS}} tests/

# Run tests with coverage report
coverage:
    uv run pytest --cov=restic_profile --cov-report=term-missing tests/

# Build distribution packages
build:
    uv build

# Serve documentation locally
docs-serve:
    uv run mkdocs serve

# Build documentation
docs-build:
    NO_MKDOCS_2_WARNING=1 uv run mkdocs build

# Install project-local Ansible collection
ansible-collection-install:
    mkdir -p .ansible/collections
    ansible-galaxy collection install --force --collections-path .ansible/collections .
    test ! -d ../ansible-collection-general || ansible-galaxy collection install --force --collections-path .ansible/collections ../ansible-collection-general

# Install the collections required by Molecule and the playbooks
ansible-requirements-install:
    mkdir -p .ansible/collections
    ansible-galaxy collection install -r requirements.yaml -p .ansible/collections

# Lint all Ansible content with ansible-lint
ansible-lint: ansible-collection-install ansible-requirements-install
    uv run ansible-lint

# Run every Molecule scenario (nested scenarios need the recursive glob)
molecule-test: ansible-collection-install ansible-requirements-install
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' uv run molecule test --all

# Run one Molecule scenario, e.g. `just molecule-test-one restic_profile/basic`
molecule-test-one scenario: ansible-collection-install ansible-requirements-install
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' uv run molecule test -s {{scenario}}

# List the Molecule scenarios
molecule-list:
    MOLECULE_GLOB='extensions/molecule/**/molecule.yml' uv run molecule list

# Build project-local Ansible collection
ansible-collection-build:
    mkdir -p .ansible/dist/
    ansible-galaxy collection build --force --output-path .ansible/dist/ .

# Remove build artifacts
clean:
    rm -rf dist/ site/ .ansible/ .cache/ .molecule/ .ruff_cache/ .pytest_cache/ htmlcov/ .coverage ansible-navigator.log
    find src/ tests/ -type f -name "*.pyc" -delete
    find src/ tests/ -type d -name "__pycache__" -delete

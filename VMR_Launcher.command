#!/bin/bash
# Virtual Manuscript Reviewer Launcher
# Double-click this file to run the GUI

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

clear
echo "========================================"
echo "   Virtual Manuscript Reviewer"
echo "========================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Function to find the best Python
find_best_python() {
    # Check for Homebrew ARM Python first
    if [ -f "/opt/homebrew/bin/python3" ]; then
        ARCH=$(file /opt/homebrew/bin/python3 | grep -o 'arm64')
        if [ -n "$ARCH" ]; then
            echo "/opt/homebrew/bin/python3"
            return
        fi
    fi

    # Check for python3 in PATH that's ARM native
    for py in python3.12 python3.11 python3.10 python3; do
        PY_PATH=$(which $py 2>/dev/null)
        if [ -n "$PY_PATH" ]; then
            ARCH=$(file "$PY_PATH" | grep -o 'arm64')
            if [ -n "$ARCH" ]; then
                echo "$PY_PATH"
                return
            fi
        fi
    done

    # Fall back to any python3
    which python3 2>/dev/null
}

PYTHON=$(find_best_python)

if [ -z "$PYTHON" ]; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    echo "Please install Python 3 from https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_ARCH=$(file $($PYTHON -c 'import sys; print(sys.executable)') | grep -o 'arm64\|x86_64' | head -1)
echo -e "Found Python $PYTHON_VERSION (${BLUE}$PYTHON_ARCH${NC})"
echo "Using: $PYTHON"
echo ""

# Check for OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    # Try to source from common profile files
    [ -f ~/.zshrc ] && source ~/.zshrc 2>/dev/null
    [ -f ~/.bash_profile ] && source ~/.bash_profile 2>/dev/null
    [ -f ~/.bashrc ] && source ~/.bashrc 2>/dev/null
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}Warning: OPENAI_API_KEY not set${NC}"
    echo ""
    echo "To use this app, you need an OpenAI API key."
    echo "Get one at: https://platform.openai.com/api-keys"
    echo ""
    read -p "Enter your OpenAI API key: " api_key
    if [ -n "$api_key" ]; then
        export OPENAI_API_KEY="$api_key"
        echo ""
        echo -e "${GREEN}API key set for this session.${NC}"
        echo ""
        echo "To make this permanent, run:"
        echo "  echo 'export OPENAI_API_KEY=\"your-key\"' >> ~/.zshrc"
        echo ""
    else
        echo -e "${RED}No API key provided. Exiting.${NC}"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# Create a virtual environment for VMR if it doesn't exist
VMR_VENV="$HOME/.vmr_venv"

if [ ! -d "$VMR_VENV" ]; then
    echo "Setting up Virtual Manuscript Reviewer environment..."
    echo "(This only happens once)"
    echo ""

    $PYTHON -m venv "$VMR_VENV"

    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create virtual environment.${NC}"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# Activate virtual environment
source "$VMR_VENV/bin/activate"

# Check if VMR is installed in the venv
if ! python -c "import virtual_manuscript_reviewer" 2>/dev/null; then
    echo ""
    echo "Installing Virtual Manuscript Reviewer..."
    echo "(This only happens once)"
    echo ""

    # Install from local directory
    if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
        pip install -e "$SCRIPT_DIR" --quiet
    else
        pip install git+https://github.com/shsoderling/Virtual-manuscript-reviewer.git --quiet
    fi

    if [ $? -ne 0 ]; then
        echo -e "${RED}Installation failed.${NC}"
        echo "Try running: pip install git+https://github.com/shsoderling/Virtual-manuscript-reviewer.git"
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo -e "${GREEN}Installation complete!${NC}"
    echo ""
fi

echo "Starting Virtual Manuscript Reviewer GUI..."
echo ""

# Run the GUI
python -m virtual_manuscript_reviewer.gui

# Keep terminal open if there was an error
if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}The application encountered an error.${NC}"
    read -p "Press Enter to exit..."
fi

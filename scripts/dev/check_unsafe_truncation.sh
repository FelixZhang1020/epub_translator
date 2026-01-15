#!/bin/bash

# Check for unsafe string truncation patterns that may break multi-byte characters
# This script detects dangerous patterns like:
#   - text[:100] + "..."  (Python)
#   - str.slice(0, N) + '...'  (JavaScript/TypeScript)
#   - str.substring(0, N) + '...'  (JavaScript/TypeScript)
#   - JSON.stringify(x).slice(...)  (JavaScript/TypeScript)

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Checking for unsafe string truncation patterns...${NC}"
echo ""

# Find the project root (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

violations_found=0
files_checked=0

# Allowed files (safe truncation utilities themselves, test files for the utilities)
ALLOWED_PATTERNS=(
    "backend/app/utils/text.py"
    "frontend/src/utils/text.ts"
    "scripts/check_unsafe_truncation.sh"
    "CLAUDE.md"
)

is_allowed_file() {
    local file="$1"
    for pattern in "${ALLOWED_PATTERNS[@]}"; do
        if [[ "$file" == *"$pattern"* ]]; then
            return 0
        fi
    done
    return 1
}

# Pattern 1: Python - text[:N] + "..." or text[:N] + '...'
# Matches patterns like: value[:100] + "...", text[:max_chars] + "..."
echo "Checking Python files for unsafe truncation..."
while IFS= read -r -d '' file; do
    ((files_checked++)) || true

    if is_allowed_file "$file"; then
        continue
    fi

    # Look for patterns like [:number] + "..." or [:variable] + "..."
    # But exclude safe patterns like hash[:16], uuid[:8], hex[:12], token[:8]
    matches=$(grep -n -E '\[:[0-9]+\]\s*\+\s*["\x27]\.{3}["\x27]|\[:\w+\]\s*\+\s*["\x27]\.{3}["\x27]' "$file" 2>/dev/null || true)

    if [[ -n "$matches" ]]; then
        # Filter out safe patterns (hash, uuid, hex, id, token patterns - typically ASCII-only)
        filtered=$(echo "$matches" | grep -v -E '(hash|uuid|hex|_id|\.id|token|key)\[:[0-9]+\]' || true)

        if [[ -n "$filtered" ]]; then
            echo -e "${RED}[VIOLATION]${NC} Unsafe truncation in: $file"
            echo "$filtered" | while read -r line; do
                echo "  $line"
            done
            ((violations_found++)) || true
        fi
    fi
done < <(find backend/app -name "*.py" -type f -print0 2>/dev/null)

# Pattern 2: TypeScript/JavaScript - .slice(0, N) + '...' or .substring(0, N) + '...'
echo "Checking TypeScript/JavaScript files for unsafe truncation..."
while IFS= read -r -d '' file; do
    ((files_checked++)) || true

    if is_allowed_file "$file"; then
        continue
    fi

    # Look for .slice(0, N) + '...' or .substring(0, N) + '...'
    matches=$(grep -n -E '\.(slice|substring)\s*\(\s*0\s*,\s*[0-9]+\s*\)\s*\+\s*["\x27]\.{3}["\x27]' "$file" 2>/dev/null || true)

    if [[ -n "$matches" ]]; then
        echo -e "${RED}[VIOLATION]${NC} Unsafe truncation in: $file"
        echo "$matches" | while read -r line; do
            echo "  $line"
        done
        ((violations_found++)) || true
    fi
done < <(find frontend/src -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -type f -print0 2>/dev/null)

# Pattern 3: JSON.stringify().slice() pattern
echo "Checking for JSON.stringify().slice() patterns..."
while IFS= read -r -d '' file; do
    if is_allowed_file "$file"; then
        continue
    fi

    matches=$(grep -n -E 'JSON\.stringify\s*\([^)]+\)\s*\.\s*slice\s*\(' "$file" 2>/dev/null || true)

    if [[ -n "$matches" ]]; then
        echo -e "${RED}[VIOLATION]${NC} Unsafe JSON truncation in: $file"
        echo "$matches" | while read -r line; do
            echo "  $line"
        done
        ((violations_found++)) || true
    fi
done < <(find frontend/src -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -type f -print0 2>/dev/null)

echo ""
echo -e "${YELLOW}Checked $files_checked files${NC}"

if [[ $violations_found -gt 0 ]]; then
    echo -e "${RED}Found $violations_found file(s) with unsafe truncation patterns!${NC}"
    echo ""
    echo "To fix, use safe truncation utilities:"
    echo ""
    echo "  Python:     from app.utils.text import safe_truncate"
    echo "              safe_truncate(text, max_chars)"
    echo ""
    echo "  TypeScript: import { safeTruncate } from '../utils/text'"
    echo "              safeTruncate(text, maxChars)"
    echo ""
    echo "See CLAUDE.md for the full Safe String Handling Policy."
    exit 1
else
    echo -e "${GREEN}No unsafe truncation patterns found!${NC}"
    exit 0
fi


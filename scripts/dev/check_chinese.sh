#!/bin/bash

# Chinese Character Check Script
# This script checks for Chinese characters in source code files
# excluding allowed locations (i18n locale files)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

found_issues=0
checked_files=0

echo -e "${YELLOW}Checking for Chinese characters in source files...${NC}"
echo ""

# Find and check files
while IFS= read -r -d '' file; do
    # Skip zh*.json files (Chinese allowed in i18n locale files)
    if [[ "$file" == *"/zh"*".json" ]] || [[ "$file" == *"/zh.json" ]]; then
        continue
    fi

    # Skip prompt template files (Chinese allowed in prompts)
    if [[ "$file" == *"/prompts/"*".md" ]]; then
        continue
    fi

    ((checked_files++)) || true

    # Check for Chinese characters using perl with Unicode support (-C flag)
    if perl -C -ne 'exit 1 if /[\x{4e00}-\x{9fff}]/' "$file" 2>/dev/null; then
        : # No Chinese found, continue
    else
        echo -e "${RED}[VIOLATION]${NC} Chinese characters found in: $file"
        perl -C -nle 'print "$.: $_" if /[\x{4e00}-\x{9fff}]/' "$file" 2>/dev/null | head -5
        echo ""
        ((found_issues++)) || true
    fi
done < <(find "$PROJECT_ROOT" \
    -path '*/node_modules/*' -prune -o \
    -path '*/venv/*' -prune -o \
    -path '*/.venv/*' -prune -o \
    -path '*/__pycache__/*' -prune -o \
    -path '*/.git/*' -prune -o \
    -path '*/dist/*' -prune -o \
    -path '*/build/*' -prune -o \
    -path '*/.claude/*' -prune -o \
    \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.sh' \) \
    -type f -print0 2>/dev/null)

echo ""
echo -e "${YELLOW}Checked $checked_files files${NC}"

if [ $found_issues -gt 0 ]; then
    echo -e "${RED}Found Chinese characters in $found_issues file(s)!${NC}"
    echo ""
    echo "Chinese characters are only allowed in:"
    echo "  - frontend/src/i18n/locales/zh.json"
    echo "  - Other **/locales/zh*.json files"
    echo "  - backend/prompts/**/*.md (prompt templates)"
    echo ""
    echo "Please move Chinese text to i18n files and use translation keys instead."
    exit 1
else
    echo -e "${GREEN}No violations found. All source files are Chinese-free!${NC}"
    exit 0
fi


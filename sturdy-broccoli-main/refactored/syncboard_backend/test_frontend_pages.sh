#!/bin/bash

# Frontend Page Crash Test
# Checks if all pages can render without TypeScript errors

echo "🧪 Testing All Frontend Pages for Crashes"
echo "========================================"
echo ""

cd frontend

# Build test
echo "📦 Running production build..."
npm run build 2>&1 | tee /tmp/build.log

BUILD_ERRORS=$(grep -i "error" /tmp/build.log | wc -l)
BUILD_WARNINGS=$(grep -i "warning" /tmp/build.log | wc -l)

echo ""
echo "📊 Build Results:"
echo "  Errors: $BUILD_ERRORS"
echo "  Warnings: $BUILD_WARNINGS"
echo ""

if [ $BUILD_ERRORS -gt 0 ]; then
    echo "❌ BUILD FAILED"
    echo ""
    echo "Errors found:"
    grep -i "error" /tmp/build.log | head -20
    exit 1
else
    echo "✅ BUILD SUCCESSFUL"
fi

# Type check
echo ""
echo "🔍 Running TypeScript type check..."
npx tsc --noEmit 2>&1 | tee /tmp/typecheck.log

TYPE_ERRORS=$(grep -E "error TS" /tmp/typecheck.log | wc -l)

echo ""
echo "📊 Type Check Results:"
echo "  Type Errors: $TYPE_ERRORS"
echo ""

if [ $TYPE_ERRORS -gt 0 ]; then
    echo "❌ TYPE CHECK FAILED"
    echo ""
    echo "Type errors found:"
    grep -E "error TS" /tmp/typecheck.log | head -20
    exit 1
else
    echo "✅ TYPE CHECK PASSED"
fi

# Count pages
PAGE_COUNT=$(find src/app -name "page.tsx" | wc -l)
LAYOUT_COUNT=$(find src/app -name "layout.tsx" | wc -l)

echo ""
echo "📄 Page Count:"
echo "  Pages: $PAGE_COUNT"
echo "  Layouts: $LAYOUT_COUNT"
echo "  Total Routes: $((PAGE_COUNT + LAYOUT_COUNT))"
echo ""

# List all pages
echo "📋 All Pages:"
find src/app -name "page.tsx" | sed 's|src/app/||' | sed 's|/page.tsx||' | sort | while read page; do
    if [ -z "$page" ]; then
        echo "  ✓ / (home)"
    else
        echo "  ✓ /$page"
    fi
done

echo ""
echo "========================================"
echo "✅ All frontend tests passed!"
echo "========================================"

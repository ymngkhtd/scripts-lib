#!/bin/bash

# Enable case-insensitive globbing for file matching
shopt -s nocaseglob
# Enable nullglob so patterns with no matches return nothing instead of the pattern string
shopt -s nullglob

# Define RAW extensions to look for
# Add other extensions here if needed
extensions=("NEF" "CR2" "ARW" "DNG" "ORF" "RAF" "CR3")

echo "Scanning $(pwd) for orphaned RAW files..."

for ext in "${extensions[@]}"; do
    # Iterate through files matching the extension
    for raw_file in *."$ext"; do
        # Ensure it is a file
        [ -f "$raw_file" ] || continue

        # Get filename without extension
        base_name="${raw_file%.*}"

        # Check for corresponding JPG/JPEG files (case-insensitive)
        # We use an array to attempt expansion of the glob patterns
        jpg_candidates=( "$base_name".jpg "$base_name".jpeg )
        
        has_jpg=false
        for candidate in "${jpg_candidates[@]}"; do
            if [ -f "$candidate" ]; then
                has_jpg=true
                break
            fi
        done

        if [ "$has_jpg" = false ]; then
            echo "Deleting orphaned RAW file: $raw_file"
            rm "$raw_file"
        fi
    done
done

echo "Done."

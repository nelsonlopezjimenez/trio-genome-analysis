#!/bin/bash

# Trio Genome Analysis Script - Chromosome-by-Chromosome Processing
# Generates full genome sequences, extracts genes, and computes SHA256 hashes
# Version 2.0 - Chromosome-based processing for 1000 Genomes data

set -e  # Exit on any error

# Configuration
REFERENCE="GRCh38.fa"
VCF_DIR="vcf_files"  # Directory containing chromosome VCF files
GTF_FILE="gencode.v46.basic.annotation.gtf"  # Gene annotation file
OUTPUT_DIR="trio_analysis"
PROTEIN_CODING_ONLY=true  # Set to true to process only protein-coding genes

# Sample IDs (adjust these to match your trio)
CHILD="NA12878"
MOTHER="NA12891"
FATHER="NA12892"

# Chromosomes to process
CHROMOSOMES=("chr1" "chr2" "chr3" "chr4" "chr5" "chr6" "chr7" "chr8" "chr9" "chr10" 
            "chr11" "chr12" "chr13" "chr14" "chr15" "chr16" "chr17" "chr18" "chr19" 
            "chr20" "chr21" "chr22" "chrX" "chrY")

# Create output directory structure
mkdir -p "$OUTPUT_DIR"/{genomes,genes,hashes,temp,logs}

# Function to create filtered GTF for protein-coding genes only
create_protein_coding_gtf() {
    echo "Creating protein-coding gene filter..."
    
    local filtered_gtf="$OUTPUT_DIR/protein_coding_genes.gtf"
    
    if [ "$PROTEIN_CODING_ONLY" = true ]; then
        # Extract only protein-coding genes from the original GTF
        if [ ! -f "$filtered_gtf" ]; then
            echo "Filtering GTF for protein-coding genes only..."
            grep 'gene_type "protein_coding"' "$GTF_FILE" | grep -w 'gene' > "$filtered_gtf"
            
            local total_genes=$(grep -w 'gene' "$GTF_FILE" | wc -l)
            local protein_genes=$(wc -l < "$filtered_gtf")
            
            echo "Filtered from $total_genes total genes to $protein_genes protein-coding genes"
            echo "Reduction: $(echo "scale=1; (1 - $protein_genes/$total_genes) * 100" | bc -l)%"
        else
            echo "Using existing protein-coding GTF: $filtered_gtf"
        fi
        
        # Update GTF_FILE to point to filtered version
        GTF_FILE="$filtered_gtf"
    else
        echo "Using all genes from original GTF"
    fi
}

echo "Starting trio genome analysis with chromosome-by-chromosome processing..."
echo "Focus: Protein-coding genes only = $PROTEIN_CODING_ONLY"

# Create protein-coding gene filter if needed
create_protein_coding_gtf
find_vcf_file() {
    local chr=$1
    # Look for VCF files containing the chromosome name
    local vcf_file=$(find "$VCF_DIR" -name "*${chr}*.vcf.gz" | head -1)
    
    if [ -z "$vcf_file" ]; then
        echo "Warning: No VCF file found for $chr in $VCF_DIR"
        return 1
    fi
    
    echo "$vcf_file"
}

# Function to generate chromosome-specific sequences
generate_chr_sequences() {
    local sample=$1
    local chr=$2
    local vcf_file=$3
    
    echo "Processing $chr for $sample..."
    
    # Create temporary chromosome-specific reference
    samtools faidx "$REFERENCE" "$chr" > "$OUTPUT_DIR/temp/${chr}_ref.fa"
    samtools faidx "$OUTPUT_DIR/temp/${chr}_ref.fa"
    
    # Generate haplotype 1 for this chromosome
    bcftools consensus \
        --sample "$sample" \
        --haplotype 1 \
        --fasta-ref "$OUTPUT_DIR/temp/${chr}_ref.fa" \
        "$vcf_file" > "$OUTPUT_DIR/temp/${sample}_${chr}_hap1.fa"
    
    # Generate haplotype 2 for this chromosome
    bcftools consensus \
        --sample "$sample" \
        --haplotype 2 \
        --fasta-ref "$OUTPUT_DIR/temp/${chr}_ref.fa" \
        "$vcf_file" > "$OUTPUT_DIR/temp/${sample}_${chr}_hap2.fa"
}

# Function to concatenate all chromosomes into full genome
concatenate_genome() {
    local sample=$1
    local haplotype=$2
    
    echo "Concatenating chromosomes for ${sample}_hap${haplotype}..."
    
    # Start with empty file
    > "$OUTPUT_DIR/genomes/${sample}_hap${haplotype}.fa"
    
    # Concatenate all chromosomes
    for chr in "${CHROMOSOMES[@]}"; do
        if [ -f "$OUTPUT_DIR/temp/${sample}_${chr}_hap${haplotype}.fa" ]; then
            cat "$OUTPUT_DIR/temp/${sample}_${chr}_hap${haplotype}.fa" >> "$OUTPUT_DIR/genomes/${sample}_hap${haplotype}.fa"
        else
            echo "Warning: Missing $chr for ${sample}_hap${haplotype}"
        fi
    done
    
    echo "Completed genome concatenation for ${sample}_hap${haplotype}"
}

# Function to generate complete genome for one individual
generate_genomes() {
    local sample=$1
    echo "Generating genome sequences for $sample..."
    
    # Process each chromosome
    for chr in "${CHROMOSOMES[@]}"; do
        vcf_file=$(find_vcf_file "$chr")
        if [ $? -eq 0 ]; then
            generate_chr_sequences "$sample" "$chr" "$vcf_file"
        fi
    done
    
    # Concatenate chromosomes into full genomes
    concatenate_genome "$sample" 1
    concatenate_genome "$sample" 2
    
    echo "Completed genome generation for $sample"
}

# Function to extract gene sequences for a specific chromosome (protein-coding optimized)
extract_chr_genes() {
    local sample=$1
    local haplotype=$2
    local chr=$3
    
    echo "Extracting protein-coding genes from $chr for ${sample}_hap${haplotype}..."
    
    # Create gene directory for this sample/haplotype
    mkdir -p "$OUTPUT_DIR/genes/${sample}_hap${haplotype}"
    
    # Count genes to process for this chromosome
    local gene_count=$(awk -v chr="$chr" '$1==chr && $3=="gene"' "$GTF_FILE" | wc -l)
    
    if [ "$gene_count" -eq 0 ]; then
        echo "  No protein-coding genes found on $chr"
        return
    fi
    
    echo "  Processing $gene_count protein-coding genes on $chr..."
    
    local processed=0
    
    # Extract gene coordinates from GTF for this chromosome
    awk -v chr="$chr" '$1==chr && $3=="gene"' "$GTF_FILE" | while read line; do
        # Parse GTF line
        chr_name=$(echo "$line" | cut -f1)
        start=$(echo "$line" | cut -f4)
        end=$(echo "$line" | cut -f5)
        strand=$(echo "$line" | cut -f7)
        
        # Extract gene_id, gene_name, and gene_type from attributes
        gene_id=$(echo "$line" | grep -o 'gene_id "[^"]*"' | cut -d'"' -f2)
        gene_name=$(echo "$line" | grep -o 'gene_name "[^"]*"' | cut -d'"' -f2 2>/dev/null || echo "$gene_id")
        gene_type=$(echo "$line" | grep -o 'gene_type "[^"]*"' | cut -d'"' -f2 2>/dev/null || echo "unknown")
        
        # Skip if essential info is missing
        [ -z "$gene_id" ] && continue
        
        # Check if we have a chromosome file for this sample/haplotype
        chr_file="$OUTPUT_DIR/temp/${sample}_${chr}_hap${haplotype}.fa"
        if [ ! -f "$chr_file" ]; then
            continue
        fi
        
        # Create descriptive filename with gene type
        output_file="$OUTPUT_DIR/genes/${sample}_hap${haplotype}/${gene_name}_${gene_id}_${gene_type}_${chr}.fa"
        
        # Extract sequence using samtools faidx
        if samtools faidx "$chr_file" "${chr_name}:${start}-${end}" > "$output_file" 2>/dev/null; then
            # Add gene information to FASTA header
            sed -i "1s/.*/>gene_name:${gene_name}|gene_id:${gene_id}|gene_type:${gene_type}|chr:${chr}|strand:${strand}|${chr_name}:${start}-${end}/" "$output_file"
            
            processed=$((processed + 1))
            if [ $((processed % 100)) -eq 0 ]; then
                echo "    Processed $processed/$gene_count genes on $chr"
            fi
        else
            rm -f "$output_file"
        fi
    done
    
    echo "  Completed: $processed protein-coding genes extracted from $chr"
}

# Function to extract gene sequences
extract_genes() {
    local sample=$1
    local haplotype=$2
    
    echo "Extracting genes for ${sample}_hap${haplotype}..."
    
    # Process each chromosome
    for chr in "${CHROMOSOMES[@]}"; do
        if [ -f "$OUTPUT_DIR/temp/${sample}_${chr}_hap${haplotype}.fa" ]; then
            # Index the chromosome file
            samtools faidx "$OUTPUT_DIR/temp/${sample}_${chr}_hap${haplotype}.fa"
            extract_chr_genes "$sample" "$haplotype" "$chr"
        fi
    done
    
    echo "Completed gene extraction for ${sample}_hap${haplotype}"
}

# Function to compute SHA256 hashes
compute_hashes() {
    local sample=$1
    local haplotype=$2
    
    echo "Computing SHA256 hashes for ${sample}_hap${haplotype}..."
    
    # Create hash file
    hash_file="$OUTPUT_DIR/hashes/${sample}_hap${haplotype}_gene_hashes.txt"
    echo "# Gene hashes for ${sample}_hap${haplotype}" > "$hash_file"
    echo "# Format: HASH GENE_FILE" >> "$hash_file"
    
    # Compute hash for each gene file
    for gene_file in "$OUTPUT_DIR/genes/${sample}_hap${haplotype}"/*.fa; do
        [ -f "$gene_file" ] || continue
        
        # Extract only sequence (no header) and compute hash
        grep -v "^>" "$gene_file" | tr -d '\n' | sha256sum | cut -d' ' -f1 > temp_hash
        hash=$(cat temp_hash)
        gene_name=$(basename "$gene_file" .fa)
        
        echo "$hash $gene_name" >> "$hash_file"
    done
    
    rm -f temp_hash
    echo "Hash computation completed for ${sample}_hap${haplotype}"
}

# Function to create summary report with protein-coding focus
create_summary() {
    echo "Creating analysis summary..."
    
    summary_file="$OUTPUT_DIR/analysis_summary.txt"
    echo "Trio Genome Analysis Summary - Protein-Coding Genes Focus" > "$summary_file"
    echo "=======================================================" >> "$summary_file"
    echo "Analysis date: $(date)" >> "$summary_file"
    echo "Protein-coding only: $PROTEIN_CODING_ONLY" >> "$summary_file"
    echo "" >> "$summary_file"
    
    if [ "$PROTEIN_CODING_ONLY" = true ]; then
        echo "Gene filtering statistics:" >> "$summary_file"
        local total_genes=$(grep -w 'gene' "$OUTPUT_DIR/../gencode.v46.basic.annotation.gtf" 2>/dev/null | wc -l || echo "unknown")
        local protein_genes=$(wc -l < "$OUTPUT_DIR/protein_coding_genes.gtf" 2>/dev/null || echo "unknown")
        echo "  Total genes in GTF: $total_genes" >> "$summary_file"
        echo "  Protein-coding genes: $protein_genes" >> "$summary_file"
        if [ "$total_genes" != "unknown" ] && [ "$protein_genes" != "unknown" ]; then
            local reduction=$(echo "scale=1; (1 - $protein_genes/$total_genes) * 100" | bc -l 2>/dev/null || echo "unknown")
            echo "  Data reduction: ${reduction}%" >> "$summary_file"
        fi
        echo "" >> "$summary_file"
    fi
    
    echo "Generated genome files:" >> "$summary_file"
    ls -lh "$OUTPUT_DIR/genomes"/*.fa 2>/dev/null >> "$summary_file" || echo "  No genome files found" >> "$summary_file"
    echo "" >> "$summary_file"
    
    echo "Gene extraction statistics:" >> "$summary_file"
    for sample in "$CHILD" "$MOTHER" "$FATHER"; do
        for hap in 1 2; do
            if [ -d "$OUTPUT_DIR/genes/${sample}_hap${hap}" ]; then
                gene_count=$(ls "$OUTPUT_DIR/genes/${sample}_hap${hap}"/*.fa 2>/dev/null | wc -l)
                echo "  ${sample}_hap${hap}: $gene_count protein-coding genes extracted" >> "$summary_file"
                
                # Show breakdown by gene type if available
                if [ "$gene_count" -gt 0 ]; then
                    echo "    Gene types:" >> "$summary_file"
                    ls "$OUTPUT_DIR/genes/${sample}_hap${hap}"/*_protein_coding_*.fa 2>/dev/null | wc -l | \
                        xargs -I {} echo "      protein_coding: {}" >> "$summary_file"
                fi
            else
                echo "  ${sample}_hap${hap}: No gene directory found" >> "$summary_file"
            fi
        done
    done
    echo "" >> "$summary_file"
    
    echo "Hash files generated:" >> "$summary_file"
    ls -lh "$OUTPUT_DIR/hashes"/*.txt 2>/dev/null >> "$summary_file" || echo "  No hash files found" >> "$summary_file"
    echo "" >> "$summary_file"
    
    echo "Storage usage:" >> "$summary_file"
    du -sh "$OUTPUT_DIR" >> "$summary_file"
    echo "" >> "$summary_file"
    
    echo "Processing completed successfully!" >> "$summary_file"
}

# Main execution
main() {
    echo "Checking prerequisites..."
    
    # Check if required files exist
    [ ! -f "$REFERENCE" ] && echo "Error: Reference file $REFERENCE not found" && exit 1
    [ ! -d "$VCF_DIR" ] && echo "Error: VCF directory $VCF_DIR not found" && exit 1
    [ ! -f "$GTF_FILE" ] && echo "Error: GTF file $GTF_FILE not found" && exit 1
    
    # Check if reference is indexed
    [ ! -f "${REFERENCE}.fai" ] && echo "Indexing reference genome..." && samtools faidx "$REFERENCE"
    
    # Check for at least one VCF file
    vcf_count=$(find "$VCF_DIR" -name "*.vcf.gz" | wc -l)
    if [ "$vcf_count" -eq 0 ]; then
        echo "Error: No VCF files found in $VCF_DIR"
        exit 1
    fi
    
    # Check for basic calculator (bc) for statistics
    if ! command -v bc &> /dev/null; then
        echo "Warning: bc calculator not found. Some statistics will be unavailable."
    fi
    
    # Create protein-coding gene filter
    create_protein_coding_gtf
    
    # Create log file
    log_file="$OUTPUT_DIR/logs/analysis_$(date +%Y%m%d_%H%M%S).log"
    exec 1> >(tee -a "$log_file")
    exec 2> >(tee -a "$log_file" >&2)
    
    # Process all trio members
    for sample in "$CHILD" "$MOTHER" "$FATHER"; do
        echo "=== Processing $sample ==="
        
        # Generate chromosome-specific sequences
        generate_genomes "$sample"
        
        # Index the final genomes
        echo "Indexing genomes for $sample..."
        samtools faidx "$OUTPUT_DIR/genomes/${sample}_hap1.fa"
        samtools faidx "$OUTPUT_DIR/genomes/${sample}_hap2.fa"
        
        # Extract genes for both haplotypes
        extract_genes "$sample" 1
        extract_genes "$sample" 2
        
        # Compute hashes for both haplotypes
        compute_hashes "$sample" 1
        compute_hashes "$sample" 2
        
        echo "=== Completed $sample ==="
    done
    
    # Clean up temporary files (optional - comment out to keep intermediate files)
    echo "Cleaning up temporary files..."
    rm -rf "$OUTPUT_DIR/temp"
    
    # Create summary report
    create_summary
    
    echo "Analysis complete! Results saved in $OUTPUT_DIR/"
    echo "Check $OUTPUT_DIR/analysis_summary.txt for details."
    echo "Log file: $log_file"
}

# Progress tracking function
show_progress() {
    local current=$1
    local total=$2
    local desc=$3
    local percent=$((current * 100 / total))
    printf "\r[%3d%%] %s (%d/%d)" "$percent" "$desc" "$current" "$total"
    if [ "$current" -eq "$total" ]; then
        echo ""
    fi
}

# Run the script
main "$@"
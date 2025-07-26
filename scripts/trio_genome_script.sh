#!/bin/bash

# Trio Genome Analysis Script
# Generates full genome sequences, extracts genes, and computes SHA256 hashes

set -e  # Exit on any error

# Configuration
REFERENCE="GRCh38.fa"
VCF_FILE="trio.vcf.gz"
GTF_FILE="gencode.gtf"  # Gene annotation file
OUTPUT_DIR="trio_analysis"

# Sample IDs (adjust these to match your trio)
CHILD="NA12878"
MOTHER="NA12891"
FATHER="NA12892"

# Create output directory
mkdir -p "$OUTPUT_DIR"/{genomes,genes,hashes}

echo "Starting trio genome analysis..."

# Function to generate genome sequences for one individual
generate_genomes() {
    local sample=$1
    echo "Generating genome sequences for $sample..."
    
    # Generate haplotype 1
    bcftools consensus \
        --sample "$sample" \
        --haplotype 1 \
        --fasta-ref "$REFERENCE" \
        "$VCF_FILE" > "$OUTPUT_DIR/genomes/${sample}_hap1.fa"
    
    # Generate haplotype 2
    bcftools consensus \
        --sample "$sample" \
        --haplotype 2 \
        --fasta-ref "$REFERENCE" \
        "$VCF_FILE" > "$OUTPUT_DIR/genomes/${sample}_hap2.fa"
    
    echo "Completed genome generation for $sample"
}

# Function to extract gene sequences
extract_genes() {
    local sample=$1
    local haplotype=$2
    
    echo "Extracting genes for ${sample}_hap${haplotype}..."
    
    # Create gene directory for this sample/haplotype
    mkdir -p "$OUTPUT_DIR/genes/${sample}_hap${haplotype}"
    
    # Extract gene coordinates from GTF and get sequences
    awk '$3=="gene"' "$GTF_FILE" | while read line; do
        # Parse GTF line
        chr=$(echo "$line" | cut -f1)
        start=$(echo "$line" | cut -f4)
        end=$(echo "$line" | cut -f5)
        
        # Extract gene_id and gene_name from attributes
        gene_id=$(echo "$line" | grep -o 'gene_id "[^"]*"' | cut -d'"' -f2)
        gene_name=$(echo "$line" | grep -o 'gene_name "[^"]*"' | cut -d'"' -f2 2>/dev/null || echo "$gene_id")
        
        # Skip if essential info is missing
        [ -z "$gene_id" ] && continue
        
        # Extract sequence using samtools faidx
        samtools faidx "$OUTPUT_DIR/genomes/${sample}_hap${haplotype}.fa" \
            "${chr}:${start}-${end}" > "$OUTPUT_DIR/genes/${sample}_hap${haplotype}/${gene_name}_${gene_id}.fa" 2>/dev/null || continue
        
        echo "Extracted gene: $gene_name ($gene_id)"
    done
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

# Function to create summary report
create_summary() {
    echo "Creating analysis summary..."
    
    summary_file="$OUTPUT_DIR/analysis_summary.txt"
    echo "Trio Genome Analysis Summary" > "$summary_file"
    echo "============================" >> "$summary_file"
    echo "Analysis date: $(date)" >> "$summary_file"
    echo "" >> "$summary_file"
    
    echo "Generated genome files:" >> "$summary_file"
    ls -lh "$OUTPUT_DIR/genomes"/*.fa >> "$summary_file"
    echo "" >> "$summary_file"
    
    echo "Gene extraction statistics:" >> "$summary_file"
    for sample in "$CHILD" "$MOTHER" "$FATHER"; do
        for hap in 1 2; do
            gene_count=$(ls "$OUTPUT_DIR/genes/${sample}_hap${hap}"/*.fa 2>/dev/null | wc -l)
            echo "  ${sample}_hap${hap}: $gene_count genes extracted" >> "$summary_file"
        done
    done
    echo "" >> "$summary_file"
    
    echo "Hash files generated:" >> "$summary_file"
    ls -lh "$OUTPUT_DIR/hashes"/*.txt >> "$summary_file"
}

# Main execution
main() {
    echo "Checking prerequisites..."
    
    # Check if required files exist
    [ ! -f "$REFERENCE" ] && echo "Error: Reference file $REFERENCE not found" && exit 1
    [ ! -f "$VCF_FILE" ] && echo "Error: VCF file $VCF_FILE not found" && exit 1
    [ ! -f "$GTF_FILE" ] && echo "Error: GTF file $GTF_FILE not found" && exit 1
    
    # Check if reference is indexed
    [ ! -f "${REFERENCE}.fai" ] && echo "Indexing reference genome..." && samtools faidx "$REFERENCE"
    
    # Check if VCF is indexed
    [ ! -f "${VCF_FILE}.tbi" ] && [ ! -f "${VCF_FILE}.csi" ] && echo "Indexing VCF file..." && bcftools index "$VCF_FILE"
    
    echo "All prerequisites met. Starting analysis..."
    
    # Generate genomes for all trio members
    for sample in "$CHILD" "$MOTHER" "$FATHER"; do
        generate_genomes "$sample"
        
        # Index the generated genomes
        samtools faidx "$OUTPUT_DIR/genomes/${sample}_hap1.fa"
        samtools faidx "$OUTPUT_DIR/genomes/${sample}_hap2.fa"
        
        # Extract genes for both haplotypes
        extract_genes "$sample" 1
        extract_genes "$sample" 2
        
        # Compute hashes for both haplotypes
        compute_hashes "$sample" 1
        compute_hashes "$sample" 2
    done
    
    # Create summary report
    create_summary
    
    echo "Analysis complete! Results saved in $OUTPUT_DIR/"
    echo "Check $OUTPUT_DIR/analysis_summary.txt for details."
}

# Run the script
main "$@"
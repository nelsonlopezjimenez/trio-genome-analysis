#!/bin/bash

# Trio Genome Analysis Script - Chromosome-by-Chromosome Processing
# Generates full genome sequences, extracts genes, and computes SHA256 hashes
# Version 2.0 - Chromosome-based processing for 1000 Genomes data

set -e  # Exit on any error

# Configuration
REFERENCE="GRCh38.fa"
VCF_DIR="vcf_files"  # Directory containing chromosome VCF files
GTF_FILE="gencode.gtf"  # Gene annotation file
OUTPUT_DIR="trio_analysis"

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

echo "Starting trio genome analysis with chromosome-by-chromosome processing..."

# Function to find VCF file for a chromosome
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
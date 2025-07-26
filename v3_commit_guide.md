# Version 3.0 Release: Protein-Coding Focus

## Step 1: Update the Main Script

Save the updated script to your repository:
```bash
# Copy the new script content to your scripts directory
cp trio_analysis_v3.sh scripts/trio_analysis.sh
chmod +x scripts/trio_analysis.sh
```

## Step 2: Update README.md

```bash
cat > README.md << 'EOF'
# Trio Genome Analysis Project

## Overview
Analysis of parent-child trio genomes from 1000 Genomes Project high-coverage data, with optimized focus on protein-coding genes for enhanced biological relevance and computational efficiency.

## Key Features
- **Protein-coding gene focus**: Reduces processing by ~65% while maintaining biological relevance
- **Chromosome-by-chromosome processing**: Handles large 1000 Genomes VCF files efficiently  
- **Separate haplotype extraction**: Tracks maternal vs paternal inheritance
- **SHA256 gene hashing**: Enables rapid comparison across individuals
- **Comprehensive logging**: Detailed progress tracking and error handling

## Goals
- Generate individual genome sequences with separate haplotypes
- Extract protein-coding gene sequences for each individual
- Compute SHA256 hashes for comparative genomic analysis
- Focus on medically and evolutionarily relevant coding regions

## Data Sources
- **1000 Genomes Project high-coverage VCF files** (GRCh38, 30x coverage)
- **NA12878 trio**: child (NA12878), mother (NA12891), father (NA12892)
- **GENCODE v46 basic annotations**: Protein-coding gene definitions

## Performance Improvements (v3.0)
- **~65% fewer genes processed**: 20,000 vs 60,000 total genomic features
- **Faster execution**: Focus on biologically relevant regions only
- **Reduced storage**: Smaller output files and hash collections
- **Enhanced metadata**: Rich gene annotations in output files

## Directory Structure
```
trio-genome-analysis/
├── scripts/              # Analysis scripts
│   └── trio_analysis.sh  # Main analysis script (v3.0)
├── data/                 # Input data (not tracked)
│   ├── vcf_files/       # Chromosome VCF files (~30GB each)
│   ├── reference/       # GRCh38 reference genome
│   └── annotations/     # GENCODE GTF files
├── docs/                # Documentation
├── results/             # Analysis outputs (not tracked)
└── trio_analysis/       # Generated results directory
    ├── genomes/         # Individual genome FASTA files
    ├── genes/           # Extracted protein-coding genes
    ├── hashes/          # SHA256 gene hashes
    └── logs/            # Analysis logs
```

## Quick Start

### Prerequisites
```bash
# Install required tools
sudo apt install bcftools samtools bc  # Ubuntu/Debian
brew install bcftools samtools bc      # macOS
```

### Data Download
```bash
# 1. Download chromosome VCF files (example for chr22)
wget "ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/working/20201028_3202_raw_GT_with_annot/20201028_CCDG_14151_B01_GRM_WGS_2020-08-05_chr22.recalibrated_variants.vcf.gz"

# 2. Download GRCh38 reference
wget "ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz"
gunzip GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz
mv GCA_000001405.15_GRCh38_no_alt_analysis_set.fna GRCh38.fa

# 3. Download GENCODE annotations
wget "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_46/gencode.v46.basic.annotation.gtf.gz"
gunzip gencode.v46.basic.annotation.gtf.gz
```

### Run Analysis
```bash
# Configure paths in the script, then run:
./scripts/trio_analysis.sh

# Results will be saved in trio_analysis/ directory
```

## Usage Notes

### Configuration Options
Edit these variables in `scripts/trio_analysis.sh`:
```bash
PROTEIN_CODING_ONLY=true     # Set to false for all genes
CHILD="NA12878"              # Child sample ID
MOTHER="NA12891"             # Mother sample ID  
FATHER="NA12892"             # Father sample ID
```

### Expected Processing Times
- **Single chromosome**: 2-4 hours (protein-coding only)
- **Full genome**: 48-96 hours total
- **Storage per trio**: ~50-100 GB (vs ~500GB for all genes)

### File Outputs
- **Genome sequences**: `{sample}_hap{1,2}.fa` (personalized genomes)
- **Gene sequences**: `{gene_name}_{gene_id}_protein_coding_{chr}.fa`
- **Hash files**: `{sample}_hap{1,2}_gene_hashes.txt`
- **Summary report**: `analysis_summary.txt`

## Version History

### v3.0 (Current) - Protein-Coding Focus
- **Major improvement**: Focus on protein-coding genes only
- **Performance**: ~65% reduction in processing time and storage
- **Enhanced metadata**: Rich gene annotations and progress tracking
- **Better error handling**: Comprehensive logging and validation

### v2.0 - Chromosome Processing
- **Scalability**: Chromosome-by-chromosome processing for large datasets
- **Memory efficiency**: Handles 1000 Genomes high-coverage data
- **Modular design**: Separate functions for each processing step

### v1.0 - Initial Implementation  
- **Basic functionality**: Single VCF file processing
- **Core features**: Genome generation, gene extraction, hashing

## Citation
If you use this tool in your research, please cite:
- The 1000 Genomes Project high-coverage dataset
- GENCODE gene annotations
- This analysis pipeline (include GitHub URL)

## Support
For issues or questions, please check the documentation in `docs/` or create an issue in this repository.
EOF
```

## Step 3: Update Documentation

```bash
# Update the data sources documentation
cat > docs/data_sources.md << 'EOF'
# Data Sources and Download Instructions (v3.0)

## Overview
Version 3.0 focuses on protein-coding genes to optimize biological relevance while reducing computational requirements.

## Required Files

### 1. High-Coverage VCF Files (1000 Genomes)
**Source**: `ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/`

**Files needed**: 
- All chromosome VCF files: `*chr*.recalibrated_variants.vcf.gz`
- Corresponding index files: `*chr*.recalibrated_variants.vcf.gz.tbi`

**File sizes** (compressed):
- chr1: ~80-100 GB (largest)
- chr2-5: ~40-80 GB each  
- chr6-22: ~20-50 GB each
- chrX: ~30-40 GB
- chrY: ~5-10 GB
- **Total: ~1.5-2 TB**

**Download strategy**:
```bash
# Start with smallest chromosome for testing
wget "ftp://...chr22.recalibrated_variants.vcf.gz"
wget "ftp://...chr22.recalibrated_variants.vcf.gz.tbi"
```

### 2. Reference Genome (GRCh38)
**Source**: NCBI or 1000 Genomes FTP
**File**: `GRCh38.fa` (~3.1 GB uncompressed)
**Requirements**: Must be indexed with `samtools faidx`

### 3. Gene Annotations (GENCODE v46)
**Source**: https://www.gencodegenes.org/
**File**: `gencode.v46.basic.annotation.gtf.gz`
**Focus**: Protein-coding genes only (automatic filtering)

**Statistics**:
- Total genes: ~60,000
- Protein-coding genes: ~20,000 (67% reduction)
- Processing improvement: ~65% faster

## Sample Information
**NA12878 Trio** (CEU population):
- **Child**: NA12878 (female)
- **Mother**: NA12891  
- **Father**: NA12892
- **Cov
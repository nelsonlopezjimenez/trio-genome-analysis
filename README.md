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
```md
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

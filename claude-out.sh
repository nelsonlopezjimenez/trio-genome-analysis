# Trio Genome Analysis - Git Repository Setup

## Initial Repository Setup

1. **Create project directory:**
```bash
mkdir trio-genome-analysis
cd trio-genome-analysis
```

2. **Initialize Git repository:**
```bash
git init
git branch -m main  # Use 'main' as default branch
```

3. **Create project structure:**
```bash
mkdir -p {scripts,data,docs,results}
mkdir -p data/{vcf_files,reference,annotations}
```

4. **Create .gitignore file:**
```bash
cat > .gitignore << 'EOF'
# Large data files
*.fa
*.fa.fai
*.vcf.gz
*.vcf.gz.tbi
*.vcf.gz.csi
*.gtf
*.gff3

# Results and temporary files
results/
trio_analysis/
*.log
temp/

# System files
.DS_Store
Thumbs.db
*.swp
*.swo
*~

# Compressed files
*.tar.gz
*.zip
*.bz2

# But keep example/small files
!data/examples/*.fa
!data/examples/*.vcf
EOF
```

5. **Create README.md:**
```bash
cat > README.md << 'EOF'
# Trio Genome Analysis Project

## Overview
Analysis of parent-child trio genomes from 1000 Genomes Project high-coverage data.

## Goals
- Generate individual genome sequences with separate haplotypes
- Extract gene sequences for each individual
- Compute SHA256 hashes for comparative analysis

## Data Sources
- 1000 Genomes Project high-coverage VCF files (GRCh38)
- NA12878 trio (child: NA12878, mother: NA12891, father: NA12892)
- GENCODE gene annotations

## Directory Structure
```
trio-genome-analysis/
├── scripts/           # Analysis scripts
├── data/             # Input data (not tracked)
│   ├── vcf_files/    # Chromosome VCF files
│   ├── reference/    # GRCh38 reference genome
│   └── annotations/  # Gene annotation files
├── docs/             # Documentation
└── results/          # Analysis outputs (not tracked)
```

## Usage
1. Download required data files
2. Run analysis script: `./scripts/trio_analysis.sh`
3. Results saved in `trio_analysis/` directory

## Version History
- v1.0: Initial single-VCF processing
- v2.0: Chromosome-by-chromosome processing for 1000G data
EOF
```

6. **Save the analysis script:**
```bash
# Copy the script content to scripts/trio_analysis.sh
cp trio_analysis.sh scripts/trio_analysis.sh
chmod +x scripts/trio_analysis.sh
```

7. **Create documentation:**
```bash
cat > docs/data_sources.md << 'EOF'
# Data Sources and Download Instructions

## Required Files

### 1. VCF Files (High-coverage 1000 Genomes)
- Location: `ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/`
- Files needed: All chromosome VCF files (chr1-22, chrX, chrY)
- Format: `*chr*.recalibrated_variants.vcf.gz` and `.tbi` files

### 2. Reference Genome
- File: GRCh38 reference genome
- Source: NCBI or 1000 Genomes FTP
- Format: FASTA (.fa)

### 3. Gene Annotations
- File: GENCODE GTF annotations
- Source: https://www.gencodegenes.org/
- Version: Latest GRCh38 release

## Sample Information
- Child: NA12878 (CEU population)
- Mother: NA12891 
- Father: NA12892
- All samples included in high-coverage dataset
EOF
```

8. **Add initial commit:**
```bash
git add .
git commit -m "Initial commit: Project setup and chromosome-based analysis script v2.0

- Added chromosome-by-chromosome processing for 1000G VCF files
- Created modular script structure with logging
- Added comprehensive documentation
- Set up proper .gitignore for large genomic files"
```

## Creating Version Tags

```bash
# Tag the current version
git tag -a v2.0 -m "Version 2.0: Chromosome-based processing"

# List all tags
git tag -l
```

## Future Commits

For each script modification:
```bash
# Make changes to scripts
git add scripts/
git commit -m "Brief description of changes"

# Create version tag if significant
git tag -a v2.1 -m "Version 2.1: Description"
```

## Remote Repository (Optional)

To backup to GitHub/GitLab:
```bash
# Create repository on GitHub, then:
git remote add origin https://github.com/yourusername/trio-genome-analysis.git
git push -u origin main
git push --tags  # Push version tags
```

## Working with Large Files

Since genomic files are large, use Git LFS if needed:
```bash
git lfs install
git lfs track "*.fa"
git lfs track "*.vcf.gz"
git add .gitattributes
git commit -m "Add Git LFS tracking for large files"
```

## Branch Strategy

Create branches for different analyses:
```bash
# Create feature branch
git checkout -b feature/admixture-analysis

# Work on new features
# ...

# Merge back to main
git checkout main
git merge feature/admixture-analysis
git tag -a v2.2 -m "Added ADMIXTURE analysis features"
```
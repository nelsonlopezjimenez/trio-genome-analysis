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
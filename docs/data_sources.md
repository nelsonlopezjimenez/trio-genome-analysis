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

**Download strategy** (start with the smallest chromosome, chr22, for testing):
```bash
wget "ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/working/20201028_3202_raw_GT_with_annot/20201028_CCDG_14151_B01_GRM_WGS_2020-08-05_chr22.recalibrated_variants.vcf.gz"
wget "ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/working/20201028_3202_raw_GT_with_annot/20201028_CCDG_14151_B01_GRM_WGS_2020-08-05_chr22.recalibrated_variants.vcf.gz.tbi"
```

## Reference Genome (GRCh38)
Source: NCBI
File: GRCh38.fa (~3.1 GB uncompressed)
Requirements: Must be indexed with samtools faidx
```bash
wget "ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz"
gunzip GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz
mv GCA_000001405.15_GRCh38_no_alt_analysis_set.fna GRCh38.fa
samtools faidx GRCh38.fa
```

## Gene Annotations (GENCODE v46)
Source: https://www.gencodegenes.org/
File: gencode.v46.basic.annotation.gtf.gz
Focus: Protein-coding genes only (automatic filtering)
```bash
wget "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_46/gencode.v46.basic.annotation.gtf.gz"
gunzip gencode.v46.basic.annotation.gtf.gz
```
## Statistics:

Total genes: ~60,000
Protein-coding genes: ~20,000 (67% reduction)
Processing improvement: ~65% faster

## Sample Information
NA12878 Trio (CEU population):

Child: NA12878 (female)
Mother: NA12891
Father: NA12892
Coverage: 30x high-coverage sequencing
Technology: Illumina NovaSeq 6000

## Storage Requirements
### Minimum Setup (Testing)

Single chromosome (chr22): ~100 GB free space
Reference + annotations: ~5 GB
Processing workspace: ~200 GB

## Full Analysis

Input data: 1.5-2 TB (all chromosomes)
Processing workspace: 500 GB - 1 TB
Final results: 50-100 GB (protein-coding only)

## Validating downloads

```bash
# VCF files
bcftools view -h data/vcf_files/*chr22*.vcf.gz | head -20

# Reference
samtools faidx data/reference/GRCh38.fa chr22:1-1000

# Annotations
head -20 data/annotations/gencode.v46.basic.annotation.gtf
grep -c 'gene_type "protein_coding"' data/annotations/gencode.v46.basic.annotation.gtf
```


# Data download
# 1. Download chromosome VCF files (example for chr22)
wget "ftp://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage/working/20201028_3202_raw_GT_with_annot/20201028_CCDG_14151_B01_GRM_WGS_2020-08-05_chr22.recalibrated_variants.vcf.gz"

# 2. Download GRCh38 reference
wget "ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz"
gunzip GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz
mv GCA_000001405.15_GRCh38_no_alt_analysis_set.fna GRCh38.fa

# 3. Download GENCODE annotations
wget "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_46/gencode.v46.basic.annotation.gtf.gz"
gunzip gencode.v46.basic.annotation.gtf.gz

## Run analysis
1. Configure paths in the script, then run:
./scripts/trio_analysis.sh

1. Results will be saved in trio_analysis/ directory

## Usage Notes
### Configuration Options
Edit these variables in scripts/trio_analysis.sh:
```sh
bashPROTEIN_CODING_ONLY=true     # Set to false for all genes
CHILD="NA12878"              # Child sample ID
MOTHER="NA12891"             # Mother sample ID  
FATHER="NA12892"             # Father sample ID
```
## Expected Processing Times

1. Single chromosome: 2-4 hours (protein-coding only)
1. Full genome: 48-96 hours total
1. Storage per trio: ~50-100 GB (vs ~500GB for all genes)

## File Outputs

1. Genome sequences: {sample}_hap{1,2}.fa (personalized genomes)
1. Gene sequences: {gene_name}_{gene_id}_protein_coding_{chr}.fa
1. Hash files: {sample}_hap{1,2}_gene_hashes.txt
1. Summary report: analysis_summary.txt

## Version History
### v3.0 (Current) - Protein-Coding Focus

1. Major improvement: Focus on protein-coding genes only
1. Performance: ~65% reduction in processing time and storage
1. Enhanced metadata: Rich gene annotations and progress tracking
1. Better error handling: Comprehensive logging and validation

v2.0 - Chromosome Processing

Scalability: Chromosome-by-chromosome processing for large datasets
Memory efficiency: Handles 1000 Genomes high-coverage data
Modular design: Separate functions for each processing step

v1.0 - Initial Implementation

Basic functionality: Single VCF file processing
Core features: Genome generation, gene extraction, hashing

## Citation
If you use this tool in your research, please cite:

The 1000 Genomes Project high-coverage dataset
GENCODE gene annotations
This analysis pipeline (include GitHub URL)

### Support
For issues or questions, please check the documentation in docs/ or create an issue in this repository.
EOF
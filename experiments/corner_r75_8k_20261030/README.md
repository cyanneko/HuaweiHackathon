# Corner R75 8k research inputs

8 train and 8 reserved dev inputs, four mechanisms paired at pressure 3/12. These are simulator research inputs, separate from final_dataset and the 100k scale train archive. Train anchors were used for single-deviation Q_R75 diagnostics; there is no trained corner network. Never fit on dev. No trace, witness, binary, or official eval registration is included. Raw input bytes are unchanged; metadata paths were made portable. See PUBLICATION_MANIFEST.json for original and public hashes.

In data_manifest.json, input_path, meta_sha256, and config_sha256 retain sanitized historical provenance and must not be used to locate public assets. Read published_input_path, published_metadata_path, published_metadata_sha256, and public_config_sha256 instead; paths are relative to this experiment directory. The archive restore_assets.py uses its own fixed-commit mapping and checks unchanged input SHA256.

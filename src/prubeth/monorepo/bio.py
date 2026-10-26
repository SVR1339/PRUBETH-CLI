"""PRUBETH Computational Biology & Biomolecular Structure Bridge.

Provides structural parsing, residue mapping, AlphaFold pLDDT confidence analysis,
and Mol* sidecar viewer manifest generation for computational biology workflows.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List

class BioComputeBridge:
    """Subsystem 17: Computational Biology & Molecular Structure Analysis Engine."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()

    def parse_pdb_structure(self, file_path: str) -> Dict[str, Any]:
        """Parses a PDB/mmCIF coordinate file and extracts residues, atoms, and B-factor metrics."""
        p = Path(file_path)
        if not p.is_absolute():
            p = self.workspace_root / p

        if not p.exists():
            return {"error": f"Structure file not found: {file_path}"}

        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        atoms = []
        residues = set()
        b_factors = []

        for line in lines:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                atom_name = line[12:16].strip()
                res_name = line[17:20].strip()
                chain = line[21:22].strip()
                res_seq = line[22:26].strip()
                
                try:
                    b_factor = float(line[60:66].strip())
                    b_factors.append(b_factor)
                except ValueError:
                    pass

                residues.add(f"{res_name}_{chain}_{res_seq}")
                atoms.append(atom_name)

        mean_b = round(sum(b_factors) / len(b_factors), 2) if b_factors else 0.0
        # If AlphaFold, B-factor corresponds to pLDDT confidence score
        plddt_category = "Very High (>90)" if mean_b >= 90 else ("Confident (70-90)" if mean_b >= 70 else "Low (<70)")

        return {
            "file": p.name,
            "total_atoms": len(atoms),
            "total_residues": len(residues),
            "mean_bfactor_plddt": mean_b,
            "structural_confidence": plddt_category,
            "chains_detected": sorted(list({r.split("_")[1] for r in residues if "_" in r}))
        }

    def generate_molstar_manifest(self, file_path: str, title: str = "Molecular Structure") -> Dict[str, Any]:
        """Generates a structure manifest formatted for 3D Biomolecular Structure Viewers (Mol*)."""
        metrics = self.parse_pdb_structure(file_path)
        return {
            "title": title,
            "structure_uri": file_path,
            "format": "pdb" if file_path.endswith(".pdb") else "mmcif",
            "metrics": metrics,
            "status": "READY_FOR_3D_RENDERING"
        }

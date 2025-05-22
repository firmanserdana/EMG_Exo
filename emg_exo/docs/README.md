# EMG_Exo Documentation

This directory contains documentation for the EMG_Exo project.

## Contents

- **Architecture.md**: Overview of the system architecture and component interactions
- **EMGSystems.md**: Details about supported EMG acquisition systems
- **SignalProcessing.md**: Documentation of signal processing techniques
- **GestureRecognition.md**: Information on gesture classification methods
- **UnityIntegration.md**: Guide to integrating with the Unity visualization
- **DeveloperGuide.md**: Guide for developers extending the system

## How to Generate Documentation

The documentation can be generated using Sphinx. To generate the documentation:

1. Install Sphinx and required packages:
```bash
pip install sphinx sphinx_rtd_theme
```

2. Generate HTML documentation:
```bash
cd docs
make html
```

3. The generated documentation will be available in `docs/_build/html/`

## Contributing to Documentation

When contributing to the documentation:

1. Use clear, concise language
2. Include code examples where appropriate
3. Add diagrams for complex concepts
4. Follow the existing structure and formatting

## Documentation TODO

- [ ] Create Sphinx configuration
- [ ] Add API documentation for each module
- [ ] Create tutorial examples
- [ ] Add diagrams for the system architecture
- [ ] Document configuration options

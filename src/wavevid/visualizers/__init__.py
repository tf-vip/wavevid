"""Visualizer modules."""
from .waveform import WaveformVisualizer
from .radial import RadialVisualizer
from .bars import BarsVisualizer
from .spectrum import SpectrumVisualizer
from .particles import ParticlesVisualizer

VISUALIZERS = {
    'waveform': WaveformVisualizer,
    'radial': RadialVisualizer,
    'bars': BarsVisualizer,
    'spectrum': SpectrumVisualizer,
    'particles': ParticlesVisualizer,
}

def get_visualizer(style: str):
    """Get visualizer class by style name."""
    return VISUALIZERS.get(style, WaveformVisualizer)

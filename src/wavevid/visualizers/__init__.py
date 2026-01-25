"""Visualizer modules."""
from .waveform import WaveformVisualizer
from .radial import RadialVisualizer
from .bars import BarsVisualizer

VISUALIZERS = {
    'waveform': WaveformVisualizer,
    'radial': RadialVisualizer,
    'bars': BarsVisualizer,
}

def get_visualizer(style: str):
    """Get visualizer class by style name."""
    return VISUALIZERS.get(style, WaveformVisualizer)

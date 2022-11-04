def classFactory(iface):
  from .gpuDataChecker import GpuDataChecker
  return GpuDataChecker(iface)

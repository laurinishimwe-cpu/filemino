from dataclasses import asdict, dataclass
from pathlib import Path
import json
@dataclass(frozen=True,slots=True)
class BenchmarkRecord:
    input_bytes:int; duration_seconds:float|None; width:int|None;height:int|None;fps:float|None;input_codec:str|None;encoder:str;preset:str;processing_seconds:float;output_bytes:int
    @property
    def realtime_speed(self): return None if not self.duration_seconds else self.processing_seconds/self.duration_seconds
    @property
    def compression_ratio(self): return None if not self.input_bytes else self.output_bytes/self.input_bytes
def append_benchmark(path:Path,record:BenchmarkRecord)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as file:file.write(json.dumps(asdict(record)|{"realtime_speed":record.realtime_speed,"compression_ratio":record.compression_ratio})+"\n")

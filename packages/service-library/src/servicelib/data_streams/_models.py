from dataclasses import dataclass

from models_library.data_streams import DataSize, DataStream, DataStreamCallable

from ..progress_bar import ProgressBarData


@dataclass(frozen=True)
class StreamData:
    data_size: DataSize
    data_stream_callable: DataStreamCallable

    async def with_progress_data_stream(
        self, progress_bar: ProgressBarData
    ) -> DataStream:
        async for chunk in self.data_stream_callable():
            await progress_bar.update(len(chunk))
            yield chunk

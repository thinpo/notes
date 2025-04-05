import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta
import os
import time
import pandas as pd

class DailyDataWriter:
    def __init__(self, output_dir="data"):
        self.output_dir = output_dir
        self.current_date = datetime.now().date()
        self.data_buffer = []
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
    
    def _get_today_filename(self) -> str:
        """生成当天文件名，格式：YYYYMMDD_data.parquet"""
        return datetime.now().strftime("%Y%m%d") + "_data.parquet"
    
    def _get_file_path(self) -> str:
        return os.path.join(self.output_dir, self._get_today_filename())
    
    def _check_date_change(self):
        """检测日期是否变化，变化时重置缓冲区"""
        today = datetime.now().date()
        if self.current_date != today:
            self.data_buffer = []
            self.current_date = today
    
    def write_record(self, timestamp, value):
        """添加记录到缓冲区并写入文件"""
        # 检测日期变化
        self._check_date_change()
        
        # 添加到内存缓冲区
        self.data_buffer.append({"timestamp": timestamp, "value": value})
        
        # 转换为 Arrow Table 并写入
        self._write_table()
        
        print(f"Data written to {self._get_file_path()}")
    
    def _write_table(self):
        """将缓冲区数据写入 Parquet 文件"""
        # 创建 DataFrame
        df = pd.DataFrame(self.data_buffer)
        
        # 转换为 Arrow Table
        table = pa.Table.from_pandas(df)
        
        # 写入 Parquet 文件
        pq.write_table(table, self._get_file_path())
    
    def close(self):
        """关闭前确保所有数据已写入"""
        if self.data_buffer:
            self._write_table()

def read_parquet_file(file_path):
    """读取并显示Parquet文件内容"""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print(f"File {file_path} doesn't exist or is empty")
        return
    
    try:
        table = pq.read_table(file_path)
        print(f"\nReading data from {file_path}:")
        print(f"Schema: {table.schema}")
        print(f"Number of rows: {len(table)}")
        print(f"Data preview:")
        print(table.to_pandas().head())
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

# 示例使用
def simulate_data_stream(writer: DailyDataWriter):
    """模拟每分钟生成数据并写入"""
    try:
        counter = 0
        while True:
            # 生成示例数据
            timestamp = datetime.now().isoformat()
            value = counter
            
            # 写入数据
            writer.write_record(timestamp, value)
            counter += 1
            
            # 读取文件内容进行测试
            read_parquet_file(writer._get_file_path())
            
            # 等待间隔
            time.sleep(5)
    except KeyboardInterrupt:
        writer.close()
        # 程序结束前，读取最后写入的数据
        read_parquet_file(writer._get_file_path())

if __name__ == "__main__":
    writer = DailyDataWriter(output_dir="daily_data")
    simulate_data_stream(writer)

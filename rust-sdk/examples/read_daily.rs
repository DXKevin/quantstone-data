use quantstone_sdk::{QuantStoneClient, ReadOptions};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let base_url = std::env::var("QUANTSTONE_API_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8000/api/v1".to_string());
    let client = QuantStoneClient::new(base_url)?;
    let table = client.read(
        "tushare.cn.stock.daily",
        &ReadOptions::new()
            .start("2026-11-01")
            .end("2026-11-24")
            .filter("ts_code", "000001.SZ"),
    )?;
    println!("rows={} columns={}", table.num_rows(), table.num_columns());
    println!("schema={:?}", table.schema());
    Ok(())
}

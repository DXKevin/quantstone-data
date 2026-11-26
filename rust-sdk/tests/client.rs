use std::sync::Arc;

use arrow::array::{Date32Array, RecordBatch, StringArray};
use arrow::datatypes::{DataType, Field, Schema};
use httpmock::prelude::*;
use parquet::arrow::ArrowWriter;
use quantstone_sdk::{DownloadOptions, Format, QuantStoneClient, ReadOptions};

fn parquet_fixture() -> Vec<u8> {
    let schema = Arc::new(Schema::new(vec![
        Field::new("trade_date", DataType::Date32, false),
        Field::new("ts_code", DataType::Utf8, false),
    ]));
    let batch = RecordBatch::try_new(
        schema.clone(),
        vec![
            Arc::new(Date32Array::from(vec![20448])),
            Arc::new(StringArray::from(vec!["000001.SZ"])),
        ],
    )
    .unwrap();
    let mut output = Vec::new();
    let mut writer = ArrowWriter::try_new(&mut output, schema, None).unwrap();
    writer.write(&batch).unwrap();
    writer.close().unwrap();
    output
}

fn client(server: &MockServer) -> QuantStoneClient {
    QuantStoneClient::new(format!("{}/api/v1", server.base_url())).unwrap()
}

#[test]
fn datasets_filters_to_active() {
    let server = MockServer::start();
    server.mock(|when, then| {
        when.method(GET).path("/api/v1/datasets");
        then.status(200)
            .header("content-type", "application/json")
            .body(r#"[{"id":"active","status":"active"},{"id":"draft","status":"draft"}]"#);
    });

    let items = client(&server).datasets().unwrap();
    assert_eq!(items.len(), 1);
    assert_eq!(items[0]["id"], "active");
}

#[test]
fn read_returns_typed_arrow_table() {
    let server = MockServer::start();
    let body = parquet_fixture();
    server.mock(|when, then| {
        when.method(GET)
            .path("/api/v1/datasets/tushare.cn.stock.daily/download")
            .query_param("start", "2026-11-24")
            .query_param("end", "2026-11-24")
            .query_param("ts_code", "000001.SZ")
            .query_param("format", "parquet");
        then.status(200)
            .header("content-type", "application/octet-stream")
            .body(&body);
    });

    let table = client(&server)
        .read(
            "tushare.cn.stock.daily",
            &ReadOptions::new()
                .start("2026-11-24")
                .end("2026-11-24")
                .filter("ts_code", "000001.SZ"),
        )
        .unwrap();
    assert_eq!(table.num_rows(), 1);
    assert_eq!(table.schema().field(1).name(), "ts_code");
    assert_eq!(
        table.batches()[0]
            .column(1)
            .as_any()
            .downcast_ref::<StringArray>()
            .unwrap()
            .value(0),
        "000001.SZ"
    );
}

#[test]
fn download_writes_selected_format() {
    let server = MockServer::start();
    server.mock(|when, then| {
        when.method(GET)
            .path("/api/v1/datasets/tushare.cn.stock.daily/download")
            .query_param("format", "csv")
            .query_param("trade_date", "2026-11-24");
        then.status(200)
            .body("trade_date,ts_code\n2026-11-24,000001.SZ\n");
    });
    let directory = tempfile::tempdir().unwrap();
    let target = directory.path().join("data.csv");
    let written = client(&server)
        .download(
            "tushare.cn.stock.daily",
            &target,
            &DownloadOptions::new()
                .filter("trade_date", "2026-11-24")
                .format(Format::Csv),
        )
        .unwrap();
    assert_eq!(written, target);
    assert_eq!(
        std::fs::read_to_string(target).unwrap(),
        "trade_date,ts_code\n2026-11-24,000001.SZ\n"
    );
}

#[test]
fn api_error_detail_is_preserved() {
    let server = MockServer::start();
    server.mock(|when, then| {
        when.method(GET)
            .path("/api/v1/datasets/test/download")
            .query_param("format", "parquet");
        then.status(422)
            .header("content-type", "application/json")
            .body(r#"{"detail":"至少填写一个主键"}"#);
    });

    let error = client(&server)
        .read("test", &ReadOptions::new())
        .unwrap_err();
    assert_eq!(error.to_string(), "至少填写一个主键");
}

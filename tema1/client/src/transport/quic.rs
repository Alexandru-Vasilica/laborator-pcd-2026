use crate::{file::DataFile, transport::Stats};
use quinn::Endpoint;
use shared::{ADDRESSES, Transport, UdpPayload, quic::make_client_config};
use std::error::Error;

pub async fn handle_quic(file: DataFile, block_size: u32) -> Result<Stats, Box<dyn Error>> {
    let address = ADDRESSES.get(&Transport::Quic).unwrap();
    let client_config = make_client_config();
    let mut endpoint = Endpoint::client("0.0.0.0:0".parse()?)?;
    endpoint.set_default_client_config(client_config);

    let connection = endpoint.connect(address.parse()?, "localhost")?.await?;

    let mut stats = Stats {
        bytes_sent: 0,
        packets_sent: 0,
    };

    let mut seq = 0u64;
    let chunk_iter = file.chunk_iter(block_size)?;
    for chunk in chunk_iter {
        let payload = UdpPayload { seq, data: chunk };
        connection.send_datagram(payload.to_bytes().into())?;
        stats.bytes_sent += payload.data.len();
        stats.packets_sent += 1;
        seq += 1;
    }
    let payload = UdpPayload { seq, data: vec![] };
    connection.send_datagram(payload.to_bytes().into())?;

    tokio::time::sleep(std::time::Duration::from_millis(100)).await;
    connection.close(0u32.into(), b"done");

    Ok(stats)
}

use crate::{file::DataFile, transport::Stats};
use quinn::Endpoint;
use shared::{ADDRESSES, Transport, UdpAck, UdpPayload, quic::make_client_config};
use std::error::Error;
use tokio::time::{Duration, timeout};

async fn send_and_wait_for_ack(
    connection: &quinn::Connection,
    stats: &mut Stats,
    payload: &UdpPayload,
) -> Result<(), Box<dyn Error>> {
    let payload_bytes = payload.to_bytes();
    for attempt in 0..5 {
        connection.send_datagram(payload_bytes.clone().into())?;
        stats.packets_sent += 1;
        stats.bytes_sent += payload.data.len();

        match timeout(Duration::from_millis(100), connection.read_datagram()).await {
            Ok(Ok(ack_bytes)) => {
                let ack = UdpAck::from_bytes(&ack_bytes);
                if ack.seq == payload.seq {
                    return Ok(());
                }
            }
            Ok(Err(e)) => return Err(e.into()),
            Err(_) => {
                if attempt + 1 == 5 {
                    return Err("Timed out waiting for QUIC datagram ack".into());
                }
            }
        }
    }
    unreachable!()
}

pub async fn handle_quic_stop_and_wait(
    file: DataFile,
    block_size: u32,
) -> Result<Stats, Box<dyn Error>> {
    let address = ADDRESSES.get(&Transport::QuicStopAndWait).unwrap();
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
        let chunk = chunk?;
        let payload = UdpPayload { seq, data: chunk };
        send_and_wait_for_ack(&connection, &mut stats, &payload).await?;
        seq += 1;
    }

    let payload = UdpPayload { seq, data: vec![] };
    connection.send_datagram(payload.to_bytes().into())?;

    tokio::time::sleep(Duration::from_millis(100)).await;
    connection.close(0u32.into(), b"done");

    Ok(stats)
}

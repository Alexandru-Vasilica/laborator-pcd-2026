use shared::{ADDRESSES, Transport, UdpAck, UdpPayload};
use tokio::net::UdpSocket;
use tokio::time::{Duration, timeout};

use crate::{file::DataFile, transport::Stats};

async fn send_and_wait_for_ack(
    socket: &UdpSocket,
    stats: &mut Stats,
    address: &str,
    payload: &UdpPayload,
) -> Result<UdpAck, std::io::Error> {
    for attempt in 0..2 {
        socket.send_to(&payload.to_bytes(), address).await?;
        stats.packets_sent += 1;
        stats.bytes_sent += payload.data.len();

        let mut ack_buffer = [0; 8];
        match timeout(Duration::from_secs(1), socket.recv_from(&mut ack_buffer)).await {
            Ok(Ok((bytes_received, _))) => {
                if bytes_received != 8 {
                    return Err(std::io::Error::new(
                        std::io::ErrorKind::Other,
                        "Invalid ack length",
                    ));
                }
                let ack = UdpAck::from_bytes(&ack_buffer);
                if ack.seq != payload.seq {
                    return Err(std::io::Error::new(
                        std::io::ErrorKind::Other,
                        "Invalid ack sequence",
                    ));
                }
                return Ok(ack);
            }
            Ok(Err(e)) => {
                return Err(e);
            }
            Err(_) => {
                if attempt + 1 == 2 {
                    return Err(std::io::Error::new(
                        std::io::ErrorKind::TimedOut,
                        "Timed out waiting for UDP ack",
                    ));
                }
            }
        }
    }

    unreachable!("retry loop always returns on final attempt")
}

pub async fn handle_udp_stop_and_wait(
    file: DataFile,
    block_size: u32,
) -> Result<Stats, std::io::Error> {
    let address = ADDRESSES.get(&Transport::UdpStopAndWait).unwrap();
    let mut seq = 0u64;
    let socket = UdpSocket::bind("0.0.0.0:0").await?;
    let mut stats = Stats {
        bytes_sent: 0,
        packets_sent: 0,
    };
    let chunk_iter = file.chunk_iter(block_size)?;
    for chunk in chunk_iter {
        let chunk = chunk?;
        let payload = UdpPayload { seq, data: chunk };
        let _ack = send_and_wait_for_ack(&socket, &mut stats, address, &payload).await?;
        seq += 1;
    }
    socket.send_to(&[], address).await?;
    Ok(stats)
}

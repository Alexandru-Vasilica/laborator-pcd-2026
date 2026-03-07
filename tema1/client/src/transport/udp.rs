use shared::{ADDRESSES, Transport};
use tokio::net::UdpSocket;

use crate::{file::DataFile, transport::Stats};

pub async fn handle_udp(file: DataFile, block_size: u32) -> Result<Stats, std::io::Error> {
    let address = ADDRESSES.get(&Transport::Udp).unwrap();
    let socket = UdpSocket::bind("0.0.0.0:0").await?;
    let mut stats = Stats {
        bytes_sent: 0,
        packets_sent: 0,
    };
    let chunk_iter = file.chunk_iter(block_size)?;
    for chunk in chunk_iter {
        let chunk = chunk?;
        socket.send_to(&chunk, address).await?;
        stats.bytes_sent += chunk.len();
        stats.packets_sent += 1;
    }
    socket.send_to(&[], address).await?;
    Ok(stats)
}

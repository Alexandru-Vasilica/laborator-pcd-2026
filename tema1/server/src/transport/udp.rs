use shared::{ADDRESSES, MAX_BLOCK_SIZE, Transport};
use tokio::net::UdpSocket;

use crate::transport::Stats;

pub async fn start_udp_server() -> Result<(), std::io::Error> {
    let address = ADDRESSES.get(&Transport::Udp).unwrap();
    let socket = UdpSocket::bind(address).await?;
    println!("UDP server started on {}", address);
    let mut stats = Stats::default();

    loop {
        let mut buff = [0; MAX_BLOCK_SIZE];
        let (bytes_received, _) = socket.recv_from(&mut buff).await?;
        println!("Received {} bytes", bytes_received);
        if bytes_received == 0 {
            println!("Stats: {:?}", stats);
            stats = Stats::default();
            continue;
        }
        stats.bytes_received += bytes_received as u64;
        stats.packets_received += 1;
    }
}

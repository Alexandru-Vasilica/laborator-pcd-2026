use shared::{ADDRESSES, MAX_BLOCK_SIZE, Transport, UdpAck, UdpPayload};
use tokio::net::UdpSocket;

use crate::transport::Stats;

pub async fn handle_udp_stop_and_wait() -> Result<(), std::io::Error> {
    let address = ADDRESSES.get(&Transport::UdpStopAndWait).unwrap();
    let socket = UdpSocket::bind(address).await?;
    println!("UDP Stop and Wait server started on {}", address);
    let mut stats = Stats::default();

    loop {
        let mut buff = [0; MAX_BLOCK_SIZE];
        let (bytes_received, addr) = socket.recv_from(&mut buff).await?;
        if bytes_received == 0 {
            println!("Stats: {:?}", stats);
            stats = Stats::default();
            continue;
        }
        let payload = UdpPayload::from_bytes(&buff);
        let ack = UdpAck { seq: payload.seq };
        socket.send_to(&ack.to_bytes(), addr).await?;
        stats.bytes_received += (bytes_received - 8) as u64;
        stats.packets_received += 1;
    }
}

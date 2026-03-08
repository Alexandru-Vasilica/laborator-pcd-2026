use crate::transport::Stats;
use quinn::Endpoint;
use shared::{ADDRESSES, Transport, UdpPayload, quic::make_server_config};
use std::error::Error;

pub async fn start_quic_server() -> Result<(), Box<dyn Error>> {
    let address = ADDRESSES.get(&Transport::Quic).unwrap();
    let server_config = make_server_config()?;
    let endpoint = Endpoint::server(server_config, address.parse()?)?;

    println!("QUIC server started on {}", address);

    while let Some(conn) = endpoint.accept().await {
        tokio::spawn(async move {
            match handle_connection(conn).await {
                Ok(stats) => println!("Protocol : {:?}, Stats: {:?}", Transport::Quic, stats),
                Err(e) => eprintln!("Error handling connection: {}", e),
            }
        });
    }

    Ok(())
}

async fn handle_connection(conn: quinn::Incoming) -> Result<Stats, Box<dyn Error>> {
    let connection = conn.await?;
    let mut stats = Stats::default();

    loop {
        match connection.read_datagram().await {
            Ok(bytes) => {
                let payload = UdpPayload::from_bytes(&bytes);
                if payload.data.is_empty() {
                    break;
                }
                stats.bytes_received += payload.data.len() as u64;
                stats.packets_received += 1;
            }
            Err(quinn::ConnectionError::ApplicationClosed(_)) => break,
            Err(e) => return Err(e.into()),
        }
    }

    Ok(stats)
}

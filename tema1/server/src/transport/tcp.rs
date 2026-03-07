use shared::{ADDRESSES, LenHeader, Transport};
use tokio::{
    io::AsyncReadExt,
    net::{TcpListener, TcpStream},
};

use crate::transport::Stats;

async fn handle_connection(mut socket: TcpStream) -> Result<Stats, std::io::Error> {
    let mut stats = Stats {
        packets_received: 0,
        bytes_received: 0,
    };
    loop {
        let mut len_header_bytes = [0; 4];
        socket.read_exact(&mut len_header_bytes).await?;
        let len_header = LenHeader::from_bytes(len_header_bytes);
        if len_header.len == 0 {
            break;
        }

        let mut buf = vec![0; len_header.len];
        socket.read_exact(&mut buf).await?;
        stats.bytes_received += buf.len() as u64;
        stats.packets_received += 1;
    }
    Ok(stats)
}

pub async fn start_tcp_server() -> Result<(), std::io::Error> {
    let address = ADDRESSES.get(&Transport::Tcp).unwrap();
    let listener = TcpListener::bind(address).await?;
    println!("TCP server started on {}", address);
    loop {
        if let Ok((socket, _)) = listener.accept().await {
            tokio::spawn(async move {
                let stats = handle_connection(socket).await;
                match stats {
                    Ok(stats) => println!("Stats: {:?}", stats),
                    Err(e) => eprintln!("Error handling connection: {}", e),
                }
            });
        }
    }
}

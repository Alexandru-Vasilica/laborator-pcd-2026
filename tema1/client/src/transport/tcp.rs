use shared::{ADDRESSES, LenHeader, Transport};
use tokio::{io::AsyncWriteExt, net::TcpStream};

use crate::{file::DataFile, transport::Stats};

pub async fn handle_tcp(file: DataFile, block_size: u32) -> Result<Stats, std::io::Error> {
    let mut stream = TcpStream::connect(ADDRESSES.get(&Transport::Tcp).unwrap()).await?;
    let mut stats = Stats {
        bytes_sent: 0,
        packets_sent: 0,
    };
    let chunk_iter = file.chunk_iter(block_size)?;
    for chunk in chunk_iter {
        let chunk = chunk?;

        let len_header = LenHeader { len: chunk.len() };
        let len_header_bytes = len_header.to_bytes();
        stream.write_all(&len_header_bytes).await?;
        stream.write_all(&chunk).await?;
        stream.flush().await?;
        stats.bytes_sent += chunk.len();
        stats.packets_sent += 1;
    }
    stream.flush().await?;
    let len_header = LenHeader { len: 0 };
    let len_header_bytes = len_header.to_bytes();
    stream.write_all(&len_header_bytes).await?;
    stream.shutdown().await?;
    Ok(stats)
}

mod file;
mod transport;

use crate::file::DataFile;
use clap::Parser;
use shared::Transport;
use std::{io, time::Instant};

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    #[arg(short, long)]
    transport: Transport,

    #[arg(short, long, default_value = "1024", value_parser = clap::value_parser!(u32).range(1..65535))]
    block_size: u32,

    #[arg(short, long)]
    file_path: String,
}

#[tokio::main]
async fn main() -> io::Result<()> {
    rustls::crypto::ring::default_provider()
        .install_default()
        .expect("Failed to install rustls crypto provider");
    let args = Args::parse();
    println!("{:?}", args);

    let file = DataFile::new(args.file_path);

    let start_time = Instant::now();
    let stats = match args.transport {
        Transport::Tcp => crate::transport::tcp::handle_tcp(file, args.block_size).await,
        Transport::Udp => crate::transport::udp::handle_udp(file, args.block_size).await,
        Transport::UdpStopAndWait => {
            crate::transport::udp_stop_and_wait::handle_udp_stop_and_wait(file, args.block_size)
                .await
        }
        Transport::Quic => {
            crate::transport::quic::handle_quic(file, args.block_size)
                .await
                .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))
        }
        Transport::QuicStopAndWait => {
            crate::transport::quic_stop_and_wait::handle_quic_stop_and_wait(file, args.block_size)
                .await
                .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))
        }
    }?;
    let end_time = Instant::now();
    let duration = end_time.duration_since(start_time);
    println!("Time taken: {:?}", duration);
    println!("Stats: {:?}", stats);
    Ok(())
}

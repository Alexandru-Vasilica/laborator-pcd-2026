use std::io;
mod transport;

#[tokio::main]
async fn main() -> io::Result<()> {
    rustls::crypto::ring::default_provider()
        .install_default()
        .expect("Failed to install rustls crypto provider");
    let tcp_task = tokio::spawn(transport::tcp::start_tcp_server());
    let udp_task = tokio::spawn(transport::udp::start_udp_server());
    let udp_stop_and_wait_task =
        tokio::spawn(transport::udp_stop_and_wait::handle_udp_stop_and_wait());
    let quic_task = tokio::spawn(async move {
        transport::quic::start_quic_server()
            .await
            .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))
    });
    let quic_stop_and_wait_task = tokio::spawn(async move {
        transport::quic_stop_and_wait::start_quic_stop_and_wait_server()
            .await
            .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))
    });
    let _ = tokio::join!(
        tcp_task,
        udp_task,
        udp_stop_and_wait_task,
        quic_task,
        quic_stop_and_wait_task
    );
    Ok(())
}

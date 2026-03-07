use std::io;
mod transport;

#[tokio::main]
async fn main() -> io::Result<()> {
    let tcp_task = tokio::spawn(transport::tcp::start_tcp_server());
    let udp_task = tokio::spawn(transport::udp::start_udp_server());
    let udp_stop_and_wait_task =
        tokio::spawn(transport::udp_stop_and_wait::handle_udp_stop_and_wait());
    let _ = tokio::join!(tcp_task, udp_task, udp_stop_and_wait_task);
    Ok(())
}

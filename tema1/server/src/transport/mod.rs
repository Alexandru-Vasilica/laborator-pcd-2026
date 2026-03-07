pub mod tcp;
pub mod udp;
pub mod udp_stop_and_wait;
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
pub struct Stats {
    packets_received: u64,
    bytes_received: u64,
}

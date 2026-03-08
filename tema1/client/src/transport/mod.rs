pub mod tcp;
pub mod udp;
pub mod udp_stop_and_wait;
pub mod quic;
pub mod quic_stop_and_wait;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Stats {
    pub packets_sent: u64,
    pub bytes_sent: usize,
}

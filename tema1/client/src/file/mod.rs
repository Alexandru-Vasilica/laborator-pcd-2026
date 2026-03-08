use std::fs::File;
use std::io::Read;

pub struct BlockIterator<'a> {
    data: &'a [u8],
    block_size: usize,
    current_pos: usize,
}

impl<'a> BlockIterator<'a> {
    pub fn new(data: &'a [u8], block_size: u32) -> Self {
        Self {
            data,
            block_size: block_size as usize,
            current_pos: 0,
        }
    }
}

impl<'a> Iterator for BlockIterator<'a> {
    type Item = Vec<u8>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.current_pos >= self.data.len() {
            return None;
        }

        let end = (self.current_pos + self.block_size).min(self.data.len());
        let chunk = self.data[self.current_pos..end].to_vec();
        self.current_pos = end;

        Some(chunk)
    }
}

pub struct DataFile {
    buffer: Vec<u8>,
}

impl DataFile {
    pub fn new(file_path: String) -> Self {
        let mut file = File::open(&file_path).expect("Failed to open data file");
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer)
            .expect("Failed to read file into memory");

        Self { buffer }
    }

    pub fn chunk_iter(&self, block_size: u32) -> Result<BlockIterator<'_>, std::io::Error> {
        Ok(BlockIterator::new(&self.buffer, block_size))
    }
}

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Set style
sns.set_theme(style="whitegrid")

# Load data - Path adjusted for script in root
csv_path = 'report/results.csv'
output_dir = 'report/'

if not os.path.exists(csv_path):
    print(f"Error: {csv_path} not found.")
    exit(1)

df = pd.read_csv(csv_path)

# 1. Time taken by protocol and block size
plt.figure(figsize=(10, 6))
df_1gb = df[df['Payload'] == '1 GB'].copy()
df_1gb['BlockSizeStr'] = df_1gb['BlockSize'].astype(str)

chart1 = sns.barplot(data=df_1gb, x='BlockSizeStr', y='TimeTaken', hue='Protocol', errorbar=None)
plt.title('Time Taken by Protocol and Block Size (1 GB Payload)')
plt.xlabel('Block Size (Bytes)')
plt.ylabel('Time Taken (seconds)')
plt.yscale('log')
plt.legend(title='Protocol', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'time_vs_protocol.png'), dpi=300)
plt.close()

# 2. Correlation between block size and data loss
plt.figure(figsize=(10, 6))
unreliable_protocols = ['udp', 'quic']
df_unreliable = df[df['Protocol'].isin(unreliable_protocols)].copy()
df_unreliable['BlockSizeStr'] = df_unreliable['BlockSize'].astype(str)

chart2 = sns.barplot(data=df_unreliable, x='BlockSizeStr', y='LossRate', hue='Protocol', errorbar=None)
plt.title('Correlation between Block Size and Data Loss')
plt.xlabel('Block Size (Bytes)')
plt.ylabel('Loss Rate (%)')
plt.legend(title='Protocol', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'loss_vs_blocksize.png'), dpi=300)
plt.close()

print(f"Charts generated in {output_dir}")

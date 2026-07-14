import torch
import torch.nn as nn
import torchvision.models as models


class ConvBlock(nn.Module):
    """conv -> BN -> ReLU 두 번"""
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class UpBlock(nn.Module):
    """업샘플 + skip connection concat + ConvBlock"""
    def __init__(self, in_ch, skip_ch, out_ch):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_ch, in_ch // 2, kernel_size=2, stride=2)
        self.conv = ConvBlock(in_ch // 2 + skip_ch, out_ch)

    def forward(self, x, skip):
        x = self.up(x)
        # 크기가 미세하게 안 맞을 수 있어서 skip 크기에 맞춰 자름
        if x.shape[-2:] != skip.shape[-2:]:
            x = nn.functional.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        x = torch.cat([x, skip], dim=1)
        return self.conv(x)


class ResNetUNet(nn.Module):
    """사전학습 ResNet34 인코더 + 직접 구현한 U-Net 디코더"""
    def __init__(self, num_classes=6, pretrained=True):
        super().__init__()
        resnet = models.resnet34(weights=models.ResNet34_Weights.DEFAULT if pretrained else None)

        # 인코더 -- 가져다 쓰는 부분
        self.stem = nn.Sequential(resnet.conv1, resnet.bn1, resnet.relu)  # /2
        self.pool = resnet.maxpool                                        # /4
        self.layer1 = resnet.layer1  # /4,  64ch
        self.layer2 = resnet.layer2  # /8,  128ch
        self.layer3 = resnet.layer3  # /16, 256ch
        self.layer4 = resnet.layer4  # /32, 512ch

        # 디코더 -- 직접 구현하는 부분
        self.up1 = UpBlock(in_ch=512, skip_ch=256, out_ch=256)  # /32 -> /16
        self.up2 = UpBlock(in_ch=256, skip_ch=128, out_ch=128)  # /16 -> /8
        self.up3 = UpBlock(in_ch=128, skip_ch=64, out_ch=64)    # /8  -> /4
        self.up4 = UpBlock(in_ch=64, skip_ch=64, out_ch=64)     # /4  -> /2

        self.final_up = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)  # /2 -> /1
        self.final_conv = nn.Conv2d(32, num_classes, kernel_size=1)

    def forward(self, x):
        x0 = self.stem(x)        # /2,  64ch  (skip으로 씀)
        x1 = self.pool(x0)       # /4
        x1 = self.layer1(x1)     # /4,  64ch  (skip)
        x2 = self.layer2(x1)     # /8,  128ch (skip)
        x3 = self.layer3(x2)     # /16, 256ch (skip)
        x4 = self.layer4(x3)     # /32, 512ch

        d1 = self.up1(x4, x3)
        d2 = self.up2(d1, x2)
        d3 = self.up3(d2, x1)
        d4 = self.up4(d3, x0)

        out = self.final_up(d4)
        out = self.final_conv(out)
        return out  # (B, num_classes, H, W)


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", device)

    model = ResNetUNet(num_classes=6, pretrained=True).to(device)

    dummy = torch.randn(2, 3, 512, 512).to(device)
    out = model(dummy)
    print("output shape:", out.shape)  # (2, 6, 512, 512) 나와야 정상
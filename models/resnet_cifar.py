import torch
import torch.nn as nn
import torch.nn.functional as F

from utils.builder import get_builder

norm_mean, norm_var = 0.0, 1.0

class LambdaLayer(nn.Module):
    def __init__(self, lambd):
        super(LambdaLayer, self).__init__()
        self.lambd = lambd

    def forward(self, x):
        return self.lambd(x)

class ResBasicBlock(nn.Module):
    expansion = 1

    def __init__(self, builder, inplanes, planes, filter_num, stride=1, deploy=False):
        super(ResBasicBlock, self).__init__()
        self.inplanes = inplanes
        self.planes = planes

        self.deploy = deploy
        if self.deploy:
            self.conv1_deploy = builder.conv3x3(planes, planes, stride, bias=True)
        else:
            self.conv1 = builder.conv_rep_conv(3, planes, planes, stride)
            self.bn1 = builder.batchnorm(planes)
            self.conv_rep1 = builder.rep_conv(3, planes, planes, stride)
            self.bn_rep1 = builder.batchnorm(planes)
            self.relu = builder.activation()

            self.conv2 = builder.conv_rep_conv(3, planes, planes)
            self.bn2 = builder.batchnorm(planes)
            self.conv_rep2 = builder.rep_conv(3, planes, planes)
            self.bn_rep2 = builder.batchnorm(planes)


        self.stride = stride
        self.shortcut = nn.Sequential()
        if stride != 1 or inplanes != planes:
            if stride != 1:
                self.shortcut = LambdaLayer(
                    lambda x: F.pad(x[:, :, ::2, ::2],
                                    (0, 0, 0, 0, (planes-inplanes)//2, planes-inplanes-(planes-inplanes)//2), "constant", 0))
            else:
                self.shortcut = LambdaLayer(
                    lambda x: F.pad(x[:, :, :, :],
                                    (0, 0, 0, 0, (planes-inplanes)//2, planes-inplanes-(planes-inplanes)//2), "constant", 0))

    def forward(self, x):
        out_a, mask = self.conv1(x)
        out_a = self.bn1(out_a)    
        out_b = self.conv_rep1(x, mask)
        out_b = self.bn_rep1(out_b)
        out = out_a + out_b

        out_a, mask = self.conv2(out)
        out_a = self.bn2(out_1)    
        out_b = self.conv_rep2(out, mask)
        out_b = self.bn_rep2(out_b)
        out = out_a + out_b

        out += self.shortcut(x)
        out = self.relu(out)

        return out

class ResNet(nn.Module):
    def __init__(self, builder, block, num_layers, num_classes=100, deploy=False):
        super(ResNet, self).__init__()
        assert (num_layers - 2) % 6 == 0, 'depth should be 6n+2'
        n = (num_layers - 2) // 6

        self.cfg_index = 0
        self.deploy = deploy
        self.inplanes = 32
        self.conv1 = nn.Conv2d(3, self.inplanes, kernel_size=3, stride=1, bias=False)
        self.bn1 = builder.batchnorm(self.inplanes)
        self.relu = builder.activation()

        self.layer1 = self._make_layer(builder, block, 32, blocks=n, stride=1)
        self.layer2 = self._make_layer(builder, block, 64, blocks=n, stride=2)
        self.layer3 = self._make_layer(builder, block, 128, blocks=n, stride=2)
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc = builder.conv1x1(128 * block.expansion, num_classes)

    def _make_layer(self, builder, block, planes, blocks, stride):
        layers = []

        layers.append(block(builder, self.inplanes, planes, filter_num=planes, stride=stride, deploy=self.deploy))
        self.cfg_index += 1

        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(builder, self.inplanes, planes, filter_num=planes, deploy=self.deploy))
            self.cfg_index += 1

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.avgpool(x)
        x = self.fc(x)
        return x.flatten(1)

def ResNet32(deploy):
    return ResNet(get_builder(), ResBasicBlock, 32, num_classes=10, deploy=deploy)

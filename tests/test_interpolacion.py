import unittest

from cliente.interpolacion import interpolar


def snap(y1, x_termo, id_termo=1):
    return {
        "jugadores": {"1": {"y": y1}, "2": {"y": 0}},
        "termos": [{"id": id_termo, "x": x_termo, "sup": 100}],
    }


class TestInterpolacion(unittest.TestCase):
    def test_punto_medio(self):
        ys, termos = interpolar(snap(100, 300), snap(200, 294), 0.5)
        self.assertEqual(ys[1], 150)
        self.assertEqual(termos[0][0], 297)

    def test_sin_previo_usa_actual(self):
        ys, termos = interpolar(None, snap(200, 294), 0.3)
        self.assertEqual(ys[1], 200)
        self.assertEqual(termos[0][0], 294)

    def test_termo_nuevo_no_se_mezcla(self):
        _, termos = interpolar(snap(0, 300, id_termo=1), snap(0, 400, id_termo=2), 0.5)
        self.assertEqual(termos[0][0], 400)


if __name__ == "__main__":
    unittest.main()
